variable "TAG" { default = "campaign/llamacpp:local" }
variable "BASE_DEVEL" {
  default = "nvidia/cuda:12.8.1-devel-ubuntu24.04@sha256:520292dbb4f755fd360766059e62956e9379485d9e073bbd2f6e3c20c270ed66"
}
# Set a full name@sha256 reference before building. No invented default digest.
variable "BASE_RUNTIME" { default = "nvidia/cuda:12.8.1-runtime-ubuntu24.04" }
variable "SOURCE_DIR" { default = "." }
variable "SOURCE_COMMIT" { default = "" }
variable "PATCH_SHA256" { default = "" }
variable "EXTRA_TARGETS" { default = "" }

group "default" { targets = ["engine"] }
target "engine" {
  context = SOURCE_DIR
  dockerfile = ".campaign-recipe/Dockerfile"
  platforms = ["linux/amd64"]
  tags = [TAG]
  args = {
    BASE_DEVEL = split("@", BASE_DEVEL)[0]
    BASE_DEVEL_DIGEST = length(split("@", BASE_DEVEL)) == 2 ? split("@", BASE_DEVEL)[1] : ""
    BASE_RUNTIME = split("@", BASE_RUNTIME)[0]
    BASE_RUNTIME_DIGEST = length(split("@", BASE_RUNTIME)) == 2 ? split("@", BASE_RUNTIME)[1] : ""
    SOURCE_COMMIT = SOURCE_COMMIT
    PATCH_SHA256 = PATCH_SHA256
    EXTRA_TARGETS = EXTRA_TARGETS
  }
  output = ["type=docker"]
  attest = ["type=provenance,mode=max"]
}
