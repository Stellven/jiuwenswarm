# Page faults and backing-store reads around first token

Pair a pinned `resource-windows.json` artifact with its request's `result.json`. The request result binds the exact counter artifact SHA-256. The capture samples immediately before sending the request, just after detecting its first streamed token, and after completion. Capture uses one fresh request per measured interval. Retain arm, prompt length, ordering, warm-up policy, cgroup identity and data availability alongside any comparison.

1. Compute three windows from monotonic timestamps. The first reaches first token, the second covers the remainder, and the third spans the whole captured request. Report the duration of each sequential snapshot read to reveal boundary skew.
2. Compute running-counter deltas independently for each source. Include memory-cgroup faults, file refaults and reclaim, cgroup block reads, process faults and storage read bytes, and whole NVMe device reads. Keep file-cache gauge changes signed.
3. Verify the process start time ticks and device identity before differencing each paired row. A changed identity, missing counter, absent controller or decreased cumulative value yields no delta. An unchanged observed counter yields zero.
4. Divide observed first-token counts and bytes by client TTFT as normalized context. Leave gauge deltas unnormalized. Retain absent or failed boundaries and excluded requests visibly.
5. Call `verify` with the exact inputs and saved report. It recomputes the report and compares each value.

Sampled counters can include background work in the relevant scope. Process and cgroup storage accounting are independent perspectives on the same interval. Keep device totals separate because they can include other processes. Refaults and major faults measure demand and reclaim activity. Readahead and existing page cache can change their relation to backing-store reads. No counter here identifies model tensor bytes or directly measures time waiting on storage.
