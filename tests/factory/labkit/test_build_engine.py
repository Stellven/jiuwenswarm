"""No Docker daemon, CUDA toolkit, GPU, or network needed."""
import argparse
import hashlib
import io
import json
import shlex
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

import jiuwenswarm.factory

sys.path.insert(0, str(Path(jiuwenswarm.factory.__file__).with_name('labkit') / 'cc' / 'build_engine'))
import build_engine as engine  # noqa: E402


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    (repo / "input.txt").write_text("original\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                    "user.email=test@example.invalid", "-c", "core.hooksPath=/dev/null",
                    "commit", "--quiet", "-m", "fixture"], check=True)
    return repo


def arguments(source, tmp_path, patch=None):
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    return argparse.Namespace(source=str(source), commit=commit, patch=patch,
                              tag="campaign/test:unit", out=str(tmp_path / "out"))


def record(args):
    return json.loads((Path(args.out) / "build-record.json").read_text())


def make_tar(path, objects):
    with tarfile.open(path, "w") as archive:
        for name, obj in objects.items():
            data = json.dumps(obj).encode()
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


def test_sha256_bytes(tmp_path):
    path = tmp_path / "payload"
    data = b"hello\x00world" * 200000
    path.write_bytes(data)
    assert engine.file_digest(path) == {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    path.write_bytes(b"")
    assert engine.file_digest(path) == {"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 0}


def test_patch_check_failure(source, tmp_path):
    patch = tmp_path / "bad.patch"
    patch.write_text("diff --git a/input.txt b/input.txt\n--- a/input.txt\n+++ b/input.txt\n@@ -1 +1 @@\n-missing\n+changed\n")
    args = arguments(source, tmp_path, str(patch))
    assert engine.build(args) == 1
    result = record(args)
    assert result["failure_stage"] == "patch_check"
    assert result["patch_sha256"] == engine.file_digest(patch)["sha256"]
    assert result["source"]["dirty"] is False
    assert (source / "input.txt").read_text() == "original\n"
    assert "patch failed" in (Path(args.out) / "build.stderr").read_text()
    assert (Path(args.out) / "build.stdout").exists()
    assert not list(Path(args.out).glob("staging-*"))


@pytest.fixture
def mock_docker(monkeypatch):
    real_run = subprocess.run
    calls = []
    state = {"fail_build": False, "staged_content": None, "jetson": False, "native_calls": [], "prefix_calls": [], "native_kwargs": [], "stats_calls": 0}

    def fake(command, **kwargs):
        if command[:3] == ["sg", "docker", "-c"]:
            state["prefix_calls"].append(command)
            command = shlex.split(command[3])
        if command[0] != "docker":
            if state["jetson"] and command[0] in ("cmake", "ninja", "nvcc", "gcc", "head", "dpkg-query", "ccache"):
                state["native_calls"].append(command)
                state["native_kwargs"].append(kwargs.copy())
                result = "test toolchain"
                if command == ["ccache", "--version"]:
                    result = "ccache version 4.5.1\n"
                if command == ["ccache", "--print-stats"]:
                    n = state["stats_calls"]
                    state["stats_calls"] += 1
                    result = f"direct_cache_hit\t{10 + n * 3}\npreprocessed_cache_hit\t2\ncache_miss\t{20 + n}\n"
                if command == ["ccache", "-s", "-v"]:
                    result = f"  Uncacheable: {state['stats_calls']} / 30 (0.0 %)\n"
                if command[:2] == ["gcc", "-print-file-name=libgomp.so.1"]:
                    library = state["libgomp"]
                    result = str(library)
                if command[:2] == ["cmake", "--build"]:
                    if state["fail_build"]:
                        kwargs["stderr"].write(b"native compile failed\n")
                        return subprocess.CompletedProcess(command, 42)
                    binaries = Path(kwargs["cwd"]) / command[2] / "bin"
                    binaries.mkdir(parents=True)
                    for tool in command[command.index("--target") + 1:]:
                        (binaries / tool).write_text("binary")
                    (binaries / "libggml.so.0").write_text("library")
                    (binaries / "libggml.so").symlink_to("libggml.so.0")
                if "-S" in command:
                    state["staged_content"] = (Path(kwargs["cwd"]) / command[command.index("-S") + 1] / "input.txt").read_text()
                kwargs["stdout"].write(result.encode())
                return subprocess.CompletedProcess(command, 0)
            return real_run(command, **kwargs)
        calls.append(command)
        stdout, stderr = kwargs["stdout"], kwargs["stderr"]
        result = ""
        code = 0
        if command[1] == "version":
            result = '{"Client":{"Version":"test"},"Server":{"Version":"test"}}'
        elif command[1:3] == ["buildx", "version"]:
            result = "buildx unit-test"
        elif command[1:3] == ["buildx", "build"]:
            app = Path(command[-1]) / "app"
            assert (app / "libggml.so").is_symlink()
            assert (app / "libggml.so.0").read_text() == "library"
            assert (app / "libgomp.so.1").exists()
            assert set(p.name for p in app.iterdir()) == set(engine.TOOLS) | set(state.get("extra_targets", [])) | {"libggml.so", "libggml.so.0", "libgomp.so.1"}
            Path(command[command.index("--metadata-file") + 1]).write_text('{"native": true}')
        elif command[1:3] == ["buildx", "bake"]:
            env = kwargs["env"]
            staged = Path(kwargs["cwd"])
            assert env["SOURCE_DIR"] == "."
            assert (staged / ".campaign-recipe" / "Dockerfile").exists()
            assert Path(command[command.index("--file") + 1]).parent == staged / ".campaign-recipe"
            assert not any(a.startswith("--allow") for a in command)  # no filesystem entitlements requested
            state["staged_content"] = (staged / "input.txt").read_text()
            if "test-backend-ops" in env.get("EXTRA_TARGETS", ""):
                assert "-DLLAMA_BUILD_TESTS=ON" in (staged / ".campaign-recipe" / "Dockerfile").read_text()
            assert not (staged / ".git").exists()
            assert "@sha256:" in env["BASE_RUNTIME"]
            result = "full compiler stdout\n"
            stderr.write(b"full compiler stderr\n")
            metadata = {"engine": {"containerimage.config.digest": "sha256:" + "1" * 64}}
            Path(command[command.index("--metadata-file") + 1]).write_text(json.dumps(metadata))
            code = 42 if state["fail_build"] else 0
        elif command[1:3] == ["image", "inspect"]:
            if command[-1].startswith("nvidia/"):
                result = json.dumps([{"RepoDigests": ["nvidia/cuda@sha256:" + "2" * 64]}])
            else:
                result = json.dumps([{"Id": "sha256:" + "1" * 64, "RepoDigests": [],
                                      "Created": "2026-01-01T00:00:00Z", "Architecture": "arm64" if state["jetson"] else "amd64", "Os": "linux"}])
        elif command[1] == "run":
            assert "--network=none" in command
            assert "--rm" in command
            assert "/bin/sh" in command and "sha256sum" in command[-1]
            assert "sha256:" + "1" * 64 in command   # hashed by immutable id, not by tag
            result = "".join("a" * 64 + "  /app/" + tool + "\n" for tool in engine.TOOLS + tuple(state.get("extra_targets", []))) + "b" * 64 + "  /app/libggml.so.0\n"
        elif command[1] == "save":
            assert command[-1] == "sha256:" + "1" * 64
            make_tar(command[command.index("--output") + 1], {"manifest.json": []})
        else:
            pytest.fail("Unexpected Docker command: " + repr(command))
        stdout.write(result.encode())
        return subprocess.CompletedProcess(command, code)

    monkeypatch.delenv("DOCKER_CMD_PREFIX", raising=False)
    monkeypatch.delenv("BUILD_JOBS", raising=False)
    monkeypatch.delenv("BASE_DEVEL", raising=False)
    monkeypatch.delenv("BASE_RUNTIME", raising=False)
    monkeypatch.setattr(subprocess, "run", fake)
    return calls, state


def test_record_schema_and_success(source, tmp_path, mock_docker):
    args = arguments(source, tmp_path)
    assert engine.build(args) == 0
    result = record(args)
    assert result["schema_version"] == 1
    assert result["status"] == "success"
    assert result["failure_stage"] is None
    assert result["source"]["commit"] == args.commit
    assert len(result["source"]["tree"]) == 40
    assert result["source"]["dirty"] is False
    assert result["patch_sha256"] is None
    assert result["platform"] == "linux/amd64"
    assert result["cmake_flags"] == engine.CMAKE_FLAGS
    assert {"Id", "RepoDigests", "Created", "Architecture", "Os", "docker_reported_id", "config_digest", "index_digest"} <= set(result["image"])
    assert set(result["tools"]) == {"/app/" + tool for tool in engine.TOOLS}
    assert "/app/libggml.so.0" in result["app_files"] and "/app/libggml.so.0" not in result["tools"]   # libraries hashed too
    # identities are distinct objects: the record must not present the docker-reported Id as the config digest
    assert result["image"]["docker_reported_id"] == result["image"]["Id"]
    assert result["archive"]["sha256"] == engine.file_digest(Path(args.out) / result["archive"]["path"])["sha256"]
    assert result["archive"]["bytes"] > 0
    assert result["base_images"]["runtime"]["digest"] == "sha256:" + "2" * 64
    assert set(result["versions"]) == {"docker", "buildx"}
    assert result["buildx_metadata"]["engine"]
    assert result["build_wall_seconds"] >= 0
    assert result["wall_seconds"] >= result["build_wall_seconds"]
    assert result["provenance"]["retained"] is False
    assert "full compiler stdout" in (Path(args.out) / "build.stdout").read_text()
    assert "full compiler stderr" in (Path(args.out) / "build.stderr").read_text()
    calls, _ = mock_docker
    assert not any("--push" in command or "prune" in command for command in calls)


def test_build_failure_preserves_logs_and_metadata(source, tmp_path, mock_docker):
    mock_docker[1]["fail_build"] = True
    args = arguments(source, tmp_path)
    assert engine.build(args) == 1
    result = record(args)
    assert result["failure_stage"] == "build"
    assert result["status"] == "failed"
    assert result["buildx_metadata"]
    assert result["build_wall_seconds"] >= 0
    assert "full compiler stdout" in (Path(args.out) / "build.stdout").read_text()
    assert "full compiler stderr" in (Path(args.out) / "build.stderr").read_text()
    assert not any(command[1] == "save" for command in mock_docker[0])


def test_valid_patch_changes_staging_only(source, tmp_path, mock_docker):
    patch = tmp_path / "good.patch"
    patch.write_text("diff --git a/input.txt b/input.txt\n--- a/input.txt\n+++ b/input.txt\n@@ -1 +1 @@\n-original\n+changed\n")
    args = arguments(source, tmp_path, str(patch))
    assert engine.build(args) == 0
    assert mock_docker[1]["staged_content"] == "changed\n"
    assert (source / "input.txt").read_text() == "original\n"
    assert record(args)["patch_sha256"] == engine.file_digest(patch)["sha256"]


@pytest.mark.parametrize("change", ["dirty", "wrong_commit"])
def test_source_rejected(source, tmp_path, change):
    args = arguments(source, tmp_path)
    if change == "dirty":
        (source / "input.txt").write_text("dirty\n")
    else:
        args.commit = "0" * 40
    assert engine.build(args) == 1
    assert record(args)["failure_stage"] == "verify_source"
    if change == "dirty":
        assert record(args)["source"]["dirty"] is True


def test_runner_captures_stdout_stderr_on_error(tmp_path):
    for name in ("build.stdout", "build.stderr"):
        (tmp_path / name).touch()
    with pytest.raises(RuntimeError):
        engine.Runner(tmp_path)([sys.executable, "-c",
                                "import sys; print('out'); print('err', file=sys.stderr); sys.exit(9)"])
    assert (tmp_path / "build.stdout").read_text() == "out\n"
    assert (tmp_path / "build.stderr").read_text() == "err\n"


@pytest.mark.parametrize("predicate,retained", [
    ("https://slsa.dev/provenance/v0.2", True),
    ("https://spdx.dev/Document", False),
])
def test_oci_provenance_requires_actual_predicate(tmp_path, predicate, retained):
    path = tmp_path / "oci.tar"
    manifest_digest, layer_digest = "3" * 64, "4" * 64
    make_tar(path, {
        "index.json": {"manifests": [{"digest": "sha256:" + manifest_digest,
                        "annotations": {"vnd.docker.reference.type": "attestation-manifest"}}]},
        "blobs/sha256/" + manifest_digest: {"layers": [{"mediaType": "application/vnd.in-toto+json",
                                                          "digest": "sha256:" + layer_digest}]},
        "blobs/sha256/" + layer_digest: {"predicateType": predicate},
    })
    assert engine.archive_provenance(path)["retained"] is retained


def test_empty_output_required(source, tmp_path):
    args = arguments(source, tmp_path)
    out = Path(args.out)
    out.mkdir()
    (out / "build-record.json").write_text("keep")
    with pytest.raises(ValueError, match="empty"):
        engine.build(args)
    assert (out / "build-record.json").read_text() == "keep"


@pytest.mark.parametrize("ccache,prefix", [(False, ""), (True, "sg docker -c")])
def test_jetson_success(source, tmp_path, mock_docker, monkeypatch, ccache, prefix):
    calls, state = mock_docker
    state["jetson"] = True
    state["libgomp"] = tmp_path / "libgomp.so.1"
    state["libgomp"].write_text("openmp")
    monkeypatch.setattr(engine.shutil, "which", lambda name: "/usr/bin/ccache" if ccache else None)
    monkeypatch.setenv("DOCKER_CMD_PREFIX", prefix)
    monkeypatch.setenv("BUILD_JOBS", "2")
    args = arguments(source, tmp_path)
    args.target = "jetson-orin"
    args.tag = "campaign/test:quoted;literal"
    assert engine.build(args) == 0
    result = record(args)
    assert result["schema_version"] == 2
    assert result["target_profile"] == "jetson-orin"
    assert result["builder"] == "host-native"
    assert result["platform"] == "linux/arm64"
    assert result["target_requirements"] == {
        "platform": "linux/arm64", "l4t_major": 36, "cuda_arch": "sm_87",
        "jetpack": ">=6.1", "runtime": "nvidia (NVIDIA_VISIBLE_DEVICES required)"}
    assert set(result["toolchain"]) == {"nvcc", "gcc", "cmake", "ninja", "nv_tegra_release", "nvidia-jetpack"}
    assert result["base_images"]["runtime"]["reference"] == engine.JETSON_RUNTIME
    assert "devel" not in result["base_images"]
    configure = next(c for c in state["native_calls"] if "-S" in c)
    assert configure[configure.index("-G") + 1] == "Ninja"
    assert configure[configure.index("-B") + 1] == ".campaign-build"
    assert configure[configure.index("-S") + 1] == "."
    for command, kwargs in zip(state["native_calls"], state["native_kwargs"]):
        if command[0] == "cmake" and command[1] != "--version":
            assert kwargs["env"]["CCACHE_BASEDIR"] == str(kwargs["cwd"])
            assert kwargs["env"]["CCACHE_NOHASHDIR"] == "1"
            assert kwargs["env"]["CCACHE_COMPILERCHECK"] == "content"
    assert (Path(args.out) / "build" / "bin" / "llama-cli").exists()
    assert result["ccache"]["enabled"] == ccache
    if ccache:
        assert result["ccache"]["version"] == "ccache version 4.5.1"
        assert result["ccache"]["before"]["hits"] == 12
        assert result["ccache"]["after"]["misses"] == 21
        assert result["ccache"]["delta"] == {"hits": 3, "misses": 1, "uncacheable": 1}
    else:
        assert result["ccache"]["before"] is None
    assert set(engine.JETSON_FLAGS) <= set(configure)
    launchers = ["-DCMAKE_" + lang + "_COMPILER_LAUNCHER=ccache" for lang in ("C", "CXX", "CUDA")]
    assert all((flag in configure) == ccache for flag in launchers)
    assert result["cmake_flags"] == engine.JETSON_FLAGS + (launchers if ccache else [])
    compile_cmd = next(c for c in state["native_calls"] if c[:2] == ["cmake", "--build"])
    assert compile_cmd[3:] == ["-j2", "--target", *engine.TOOLS]
    image_cmd = next(c for c in calls if c[1:3] == ["buildx", "build"])
    assert image_cmd[image_cmd.index("--platform") + 1] == "linux/arm64"
    assert "--load" in image_cmd
    build_args = dict(image_cmd[i + 1].split("=", 1) for i, v in enumerate(image_cmd) if v == "--build-arg")
    assert build_args == {"BASE_RUNTIME": engine.JETSON_RUNTIME, "SOURCE_COMMIT": args.commit,
                          "SOURCE_TREE": result["source"]["tree"], "PATCH_SHA256": "",
                          "TOOLCHAIN": json.dumps(result["toolchain"], sort_keys=True), "TARGET_PROFILE": "jetson-orin"}
    hash_cmd = next(c for c in calls if c[1] == "run")
    assert hash_cmd[hash_cmd.index("--runtime") + 1] == "runc"
    assert bool(state["prefix_calls"]) == bool(prefix)
    if prefix:
        assert len(state["prefix_calls"]) == len(calls)
    assert state["staged_content"] == "original\n"
    assert not list(Path(args.out).glob("staging-*"))


@pytest.mark.parametrize("cached", [False, True])
def test_jetson_native_failure(source, tmp_path, mock_docker, monkeypatch, cached):
    calls, state = mock_docker
    state.update(jetson=True, fail_build=True)
    monkeypatch.setattr(engine.shutil, "which", lambda name: "/usr/bin/ccache" if cached else None)
    args = arguments(source, tmp_path)
    args.target = "jetson-orin"
    assert engine.build(args) == 1
    result = record(args)
    assert result["failure_stage"] == "build"
    if cached:
        assert result["ccache"]["after"]["hits"] == 15
    assert result["toolchain"]["nvcc"]
    assert result["build_wall_seconds"] >= 0
    assert not any(c[1:3] == ["buildx", "build"] for c in calls)
    assert "native compile failed" in (Path(args.out) / "build.stderr").read_text()


def test_jetson_dockerfile():
    text = (engine.JETSON_RECIPES / "Dockerfile").read_text()
    assert "ARG BASE_RUNTIME=" + engine.JETSON_RUNTIME in text
    for fragment in ("FROM ${BASE_RUNTIME}", "COPY app/ /app/", "LD_LIBRARY_PATH=/app",
                     "NVIDIA_VISIBLE_DEVICES=all", "NVIDIA_DRIVER_CAPABILITIES=compute,utility",
                     "ENTRYPOINT []", "${SOURCE_TREE}", "${SOURCE_COMMIT}", "${PATCH_SHA256}",
                     "${TOOLCHAIN}", "${TARGET_PROFILE}"):
        assert fragment in text


def test_snapshot_python310_fallback(tmp_path, monkeypatch):
    monkeypatch.delattr(tarfile, "data_filter", raising=False)
    path = tmp_path / "source.tar"
    make_tar(path, {"file": "content"})
    dest = tmp_path / "extracted"
    dest.mkdir()
    with tarfile.open(path) as archive:
        engine.extract_snapshot(archive, dest)
    assert json.loads((dest / "file").read_text()) == "content"
    with tarfile.open(path, "w") as archive:
        link = tarfile.TarInfo("escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "../outside"
        archive.addfile(link)
    with tarfile.open(path) as archive, pytest.raises(ValueError, match="Unsafe archive link"):
        engine.extract_snapshot(archive, dest)


def test_tests_target_requires_option(source, tmp_path):
    args = arguments(source, tmp_path)
    args.extra_target = ['test-backend-ops']
    with pytest.raises(ValueError, match='requires --with-tests'):
        engine.build(args)


@pytest.mark.parametrize('jetson', [False, True])
def test_with_tests_build_and_record(source, tmp_path, mock_docker, monkeypatch, jetson):
    calls, state = mock_docker
    state['jetson'] = jetson
    state['libgomp'] = tmp_path / 'libgomp.so.1'
    state['libgomp'].write_text('openmp')
    monkeypatch.setattr(engine.shutil, 'which', lambda name: None)
    args = arguments(source, tmp_path)
    args.with_tests = True
    args.extra_target = ['test-backend-ops']
    state['extra_targets'] = args.extra_target
    if jetson:
        args.target = 'jetson-orin'
    assert engine.build(args) == 0
    result = record(args)
    assert result['with_tests'] is True
    assert result['extra_targets'] == ['test-backend-ops']
    assert '-DLLAMA_BUILD_TESTS=ON' in result['cmake_flags']
    assert '-DLLAMA_BUILD_TESTS=OFF' not in result['cmake_flags']
    assert '/app/test-backend-ops' in result['tools']
    if jetson:
        configure = next(c for c in state['native_calls'] if '-S' in c)
        assert '-DLLAMA_BUILD_TESTS=ON' in configure
        compile_cmd = next(c for c in state['native_calls'] if c[:2] == ['cmake', '--build'])
        assert 'test-backend-ops' in compile_cmd
    else:
        assert 'staged_recipes' in result
