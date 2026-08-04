$adapter = Get-NetAdapter -Physical | Where-Object { $_.InterfaceDescription -eq 'Realtek PCIe GbE Family Controller' }
if (-not $adapter) {
    Write-Host 'Realtek PCIe GbE adapter not found'
    exit 1
}
$ifIndex = $adapter.ifIndex
# Remove existing IP addresses on this adapter
Get-NetIPAddress -InterfaceIndex $ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
# Set static IP
New-NetIPAddress -InterfaceIndex $ifIndex -IPAddress 192.168.100.1 -PrefixLength 24 -DefaultGateway 192.168.100.254 | Out-Null
# Set DNS
Set-DnsClientServerAddress -InterfaceIndex $ifIndex -ServerAddresses ('114.114.114.114','8.8.8.8') | Out-Null
Write-Host "Set static IP 192.168.100.1/24 on adapter: $($adapter.Name)"
Get-NetIPAddress -InterfaceIndex $ifIndex -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength
