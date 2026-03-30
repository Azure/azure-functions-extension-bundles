param(
     [Parameter()]
     [string]$StorageAccountName,
 
     [Parameter()]
     [string]$StorageAccountKey,

     [Parameter()]
     [string]$bundleId
 )

$ctx = New-AzureStorageContext -StorageAccountName $StorageAccountName -StorageAccountKey $StorageAccountKey
$files = Get-ChildItem -Recurse -Path "../artifacts"
foreach ($file in $files) {
    $fileName = $file.FullName.ToLower();
    if ($fileName.Contains("cdnprod")) {
        $fileFullName = $file.FullName
        Write-Host "Extracting file:$fileFullName"
        Expand-Archive -LiteralPath $fileFullName -DestinationPath ".\cdnProd"
    }
}

$files = Get-ChildItem -Recurse -Path ".\cdnProd" -File
Set-Location .\cdnProd
foreach ($file in $files) {
    $fileFullName = $file.FullName
    $fileName = $file.FullName.ToLower();
    if (-not $fileName.Contains("index")) {
        $relativePath = Resolve-Path -Relative $fileFullName
        $relativePath = $relativePath.Replace(".\", "")
        $blobName = "ExtensionBundles\" + $relativePath
        Write-Host "Uploading file: $blobName" 
        Set-AzureStorageBlobContent -Container "public" -File $fileFullName -Blob $blobName -Context $ctx -Force
    }
}

$otherVersionsExist = $false
mkdir ".\existingjsons"
$previousDirectory = $pwd

foreach ($file in $files) {
    $fileName = $file.FullName.ToLower();
    if ($fileName.Contains("cdnprod")) {
        $fileFullName = $file.FullName
        Write-Host "Uploading file:$fileFullName"
        Expand-Archive -LiteralPath $fileFullName -DestinationPath ".\cdnProd"
    }
}

$files = Get-ChildItem -Recurse -Path ".\cdnProd" -File
Set-Location .\cdnProd

# Try and download existing json files in storage
try {
    Get-AzureStorageBlobContent -Container "public" -Blob "ExtensionBundles\$bundleId\index.json" -Destination "$previousDirectory\existingjsons" -Context $ctx
    $otherVersionsExist = $true
    Write-Host "Existing index files present"
}
catch {
    Write-Host "Maybe index.json does not exist"
}

foreach ($file in $files) {
    $fileFullName = $file.FullName
    $fileName = $file.FullName.ToLower();
    $relativePath = Resolve-Path -Relative $fileFullName
    $relativePath = $relativePath.Replace(".\", "")
    $blobName = "ExtensionBundles\" + $relativePath
    Write-Host "Uploading file: $blobName" 
        
    if ($fileName.Contains("index")) {
        
        if (-not $otherVersionsExist) {
            Set-AzureStorageBlobContent -Container "public" -File $fileFullName -Blob $blobName -Context $ctx -Force
            exit
        }
               
        $indexExisting = [System.IO.File]::ReadAllText("$previousDirectory\\existingjsons\\ExtensionBundles\\$bundleId\\index.json") | ConvertFrom-Json
        $newIndex = [System.IO.File]::ReadAllText("$fileFullName") | ConvertFrom-Json

        #initialize
        $resultingArray = New-Object System.Collections.Generic.HashSet[string]

        
        foreach ($value in $indexExisting) {
            $resultingArray.Add($value)
        }

        $resultingArray.Add($newValue)

        #merge
        foreach ($newValue in $newIndex) {
            $resultingArray.Add($newValue)
        }

        #convert merged to json
        $combinedIndex = $resultingArray | ConvertTo-Json -Depth 100 -Compress

        #overwrite existing file
        $combinedIndex | Out-File -FilePath $fileFullName -encoding "utf8nobom"
        
            
        Set-AzureStorageBlobContent -Container "public" -File $fileFullName -Blob $blobName -Context $ctx -Force
    }
}