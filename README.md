# RigBench

A safe, repeatable local benchmark tool for Windows and Linux. Python standard library only.

## Requirements
- Python 3.10+ recommended (no pip packages required)
- Windows 10/11 or Linux
- No admin rights, network access, or hardware purchases required

## Windows quick start
1. Install Python from https://www.python.org/downloads/ if needed. Enable **Add python.exe to PATH** during setup.
2. Extract this ZIP.
3. Open PowerShell in the extracted `ghostbench_mvp` folder.
4. Run:

```powershell
py --version
py ghostbench.py system
py ghostbench.py bench cpu --runs 5 --label baseline
py ghostbench.py bench memory --runs 5 --label baseline
```

Each benchmark prints the path to its JSON results file in `results`.

Generate a report (replace the example with the real path printed by the program):

```powershell
py ghostbench.py report results\cpu_YYYYMMDD_HHMMSS_XXXXXX.json
```

## Controlled comparison
Run the same test before and after changing exactly one setting. Keep parameters identical:

```powershell
py ghostbench.py bench cpu --runs 5 --label baseline --output results\cpu_baseline.json
py ghostbench.py bench cpu --runs 5 --label candidate --output results\cpu_candidate.json
py ghostbench.py compare results\cpu_baseline.json results\cpu_candidate.json --output results\comparison.json
```

These commands alone only test repeatability; they do not prove an optimization helped. Make and document one controlled change between the two sets of measurements.

## Commands
- `system`: system, Python and physical memory information
- `bench cpu`: deterministic Python integer loop
- `bench memory`: allocate a bounded bytearray and overwrite it in blocks
- `compare BASELINE CANDIDATE`: compare results with matching workload parameters
- `report FILE`: generate a self-contained HTML report

## Safety and scientific validity
- Memory benchmark defaults to 128 MiB and is capped at 512 MiB.
- CPU iterations are capped at 100 million.
- No files are deleted, no services or boot settings are changed, and administrator access is not required.
- Close heavy applications; keep power mode and environment consistent.
- Run tests several times and report median and spread, not just the best run.
- CPU results measure Python interpreter performance, not a universal hardware CPU score.
- Memory results measure Python allocation and block-write behavior, not pure DRAM bandwidth.
- Do not compare runs with different parameters as if they were equivalent.
- Review reports before sharing because they include system and software details.

## Project structure
```text
ghostbench_mvp/
├── ghostbench.py
├── README.md
├── LICENSE
├── results/
└── tests/
    └── test_ghostbench.py
```

## Roadmap
1. Add test coverage and result schema validation.
2. Add repeatable workload manifests and environment metadata.
3. Add Linux-specific system collectors.
4. Add a safe, manual configuration experiment workflow (no automatic system changes).
