$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Levels = @("0_2", "0_3", "0_4", "0_5", "0_6", "0_7", "0_8", "0_9")
$RunRoot = Join-Path $ProjectRoot "results\parser_runs\parser_eval\lilac_run_logs"
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null

foreach ($Level in $Levels) {
    $StartedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$StartedAt] START level $Level" | Tee-Object -FilePath (Join-Path $RunRoot "runner_status.log") -Append

    $LogFile = Join-Path $RunRoot "run_lilac_$Level.log"
    python (Join-Path $ProjectRoot "Code\eval_parsers.py") `
        --parsers LILAC `
        --levels $Level `
        --allow-lilac-api *> $LogFile

    if ($LASTEXITCODE -ne 0) {
        $FailedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        "[$FailedAt] FAILED level $Level exit=$LASTEXITCODE" | Tee-Object -FilePath (Join-Path $RunRoot "runner_status.log") -Append
        exit $LASTEXITCODE
    }

    $FinishedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$FinishedAt] FINISH level $Level" | Tee-Object -FilePath (Join-Path $RunRoot "runner_status.log") -Append
}

$DoneAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$DoneAt] ALL_DONE" | Tee-Object -FilePath (Join-Path $RunRoot "runner_status.log") -Append
