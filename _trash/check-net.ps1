Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' } | Select-Object Name,InterfaceDescription,LinkSpeed
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' } | Select-Object InterfaceAlias,IPAddress,PrefixLength
