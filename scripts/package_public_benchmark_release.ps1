param(
    [string]$GroundTruthRun = "2800af31-ae35-4d12-af1d-dd5f4ed17223",
    [string]$StressRun = "5357f529-6c14-40e8-b3ad-027cd06539a8",
    [string]$ReportRoot = "reports\neural_classical_workstation",
    [string]$SummaryRoot = "benchmark_experiment\results\neural_classical_workstation",
    [string]$OutputRoot = "release_artifacts\neural_classical_workstation"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$groundTruthPath = Join-Path $ReportRoot $GroundTruthRun
$stressPath = Join-Path $ReportRoot $StressRun

if (-not (Test-Path $groundTruthPath)) {
    throw "Ground-truth report path not found: $groundTruthPath"
}
if (-not (Test-Path $stressPath)) {
    throw "Stress report path not found: $stressPath"
}
if (-not (Test-Path $SummaryRoot)) {
    throw "Public summary path not found: $SummaryRoot"
}

$archives = @(
    @{
        Name = "neural_classical_workstation_public_summaries.zip"
        Path = $SummaryRoot
    },
    @{
        Name = "neural_classical_workstation_ground_truth_report.zip"
        Path = $groundTruthPath
    },
    @{
        Name = "neural_classical_workstation_stress_report_core.zip"
        Path = @(
            Join-Path $stressPath "html"
            Join-Path $stressPath "figures"
            Join-Path $stressPath "latex"
            Join-Path $stressPath "manifest"
            Join-Path $stressPath "run_summary.json"
            Join-Path $stressPath "tables\leaderboard.csv"
            Join-Path $stressPath "tables\uncertainty_calibration.csv"
            Join-Path $stressPath "tables\estimator_metadata.csv"
            Join-Path $stressPath "tables\run_summary.csv"
        )
    }
)

foreach ($archive in $archives) {
    $destination = Join-Path $OutputRoot $archive.Name
    if (Test-Path $destination) {
        Remove-Item -LiteralPath $destination
    }
    Compress-Archive -Path $archive.Path -DestinationPath $destination -CompressionLevel Optimal
}

$checksumPath = Join-Path $OutputRoot "checksums.sha256.txt"
if (Test-Path $checksumPath) {
    Remove-Item -LiteralPath $checksumPath
}

Get-ChildItem -Path $OutputRoot -Filter "*.zip" |
    Sort-Object Name |
    ForEach-Object {
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
        "$($hash.Hash.ToLowerInvariant())  $($_.Name)"
    } |
    Set-Content -Path $checksumPath -Encoding ascii

Get-ChildItem -Path $OutputRoot | Select-Object Name, Length
