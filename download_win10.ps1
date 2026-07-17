$outputPath = "E:\ClaudeCode\seb-bypass"
$url = "https://software-download.microsoft.com/sg/download/iso?cid=6670770c30f04cfa95476e946ddfb8e2"

Write-Host "Downloading Windows 10 ISO (this is ~5.7 GB, may take a while)..."
Write-Host "URL: $url"
Write-Host "Output: $outputPath\Win10_22H2.iso"
Write-Host ""

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($url, "$outputPath\Win10_22H2.iso")
    $size = (Get-Item "$outputPath\Win10_22H2.iso").Length
    Write-Host "Download complete! Size: $([math]::Round($size/1GB, 2)) GB"
} catch {
    Write-Host "Download failed: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "Alternative: Please download Windows 10 ISO manually from:"
    Write-Host "https://www.microsoft.com/en-us/software-download/windows10ISO"
    Write-Host "Then save it to: $outputPath"
}
