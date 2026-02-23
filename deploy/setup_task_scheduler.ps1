# setup_task_scheduler.ps1
# Register Windows Task Scheduler job to send LINE deadline alerts daily at 08:00
# Run as Administrator on the production server (C:\project\project_tracker)

$python  = "C:\project\project_tracker\venv\Scripts\python.exe"
$manage  = "C:\project\project_tracker\manage.py"
$workDir = "C:\project\project_tracker"
$taskName = "ProjectTracker-DeadlineAlerts"

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "$manage send_deadline_alerts" `
    -WorkingDirectory $workDir

$trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable $true `
    -RunOnlyIfNetworkAvailable $true

# Run as SYSTEM so no password needed
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Send LINE deadline alerts daily at 8am (ProjectTracker Phase 3)" `
    -Force

Write-Host "Scheduled task '$taskName' registered successfully." -ForegroundColor Green
Write-Host "To test immediately: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "To view logs:        Get-ScheduledTaskInfo -TaskName '$taskName'"
