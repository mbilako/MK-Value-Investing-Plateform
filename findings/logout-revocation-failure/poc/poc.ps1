$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$sessionCookie = "mkvip_session=demo-session"
$serverSessionActive = $true
$browserCookie = $sessionCookie
$user = @{
    id = "00000000-0000-0000-0000-000000000001"
    email = "victim@example.test"
}

function Invoke-DemoLogout {
    param(
        [bool] $SessionActive,
        [string] $Cookie
    )

    if (-not $SessionActive -or $Cookie -ne $sessionCookie) {
        throw "The demo did not start with a valid session."
    }

    # Simulate HTTP 503 before the backend deletes the server session or
    # expires the browser cookie.
    $failure = [System.InvalidOperationException]::new(
        "POST /auth/logout returned 503"
    )
    $failure.Data["Status"] = 503
    throw $failure
}

function Invoke-DemoAuthMe {
    param(
        [bool] $SessionActive,
        [string] $Cookie
    )

    if (-not $SessionActive -or $Cookie -ne $sessionCookie) {
        throw "/auth/me returned 401"
    }

    return $user
}

$uiStatus = "authenticated"
$uiUser = $user
Write-Output "[+] initial state: $uiStatus as $($uiUser.email)"

# Mirrors App.logout(): the exception is swallowed, then the UI state is
# unconditionally cleared in the finally block.
try {
    Invoke-DemoLogout `
        -SessionActive $serverSessionActive `
        -Cookie $browserCookie
}
catch {
    Write-Output "[+] POST /auth/logout returned $($_.Exception.Data["Status"])"
}
finally {
    $uiUser = $null
    $uiStatus = "unauthenticated"
}

Write-Output "[+] vulnerable UI state after failure: $uiStatus"
Write-Output "[+] browser cookie retained: $browserCookie"

# Mirrors application startup: /auth/me reuses the retained HttpOnly cookie.
$uiUser = Invoke-DemoAuthMe `
    -SessionActive $serverSessionActive `
    -Cookie $browserCookie
$uiStatus = "authenticated"

Write-Output "[+] reload /auth/me returned 200"
Write-Output "[+] restored state: $uiStatus as $($uiUser.email)"

if (-not $serverSessionActive) {
    throw "The server session was unexpectedly revoked."
}
if ($browserCookie -ne $sessionCookie) {
    throw "The browser cookie was unexpectedly removed."
}
if ($uiUser.email -ne $user.email) {
    throw "The previous account was not restored."
}

Write-Output "[+] demonstration complete: fail-open logout confirmed"
