<#
.SYNOPSIS
Downgrade Mascot Distiller processing options (.opt) files from schema 1.7+ to 1.6.

.DESCRIPTION
For each input .opt file the script:
  - Sets the minorVersion attribute on <processingOptions> to "6"
  - Removes elements introduced after schema 1.6:
      <precursorIonMobilityGroupTol>             added in 1.7
      <vendorOption type="11" option="bSumIMS">  added in 1.9 (Waters)
      <vendorOption type="12" option="MinPeakArea"> added in 1.9 (Sciex)
  - Writes the result to a sibling file with "_1_6" inserted immediately
    before the trailing ".<vendor>.opt" (e.g. Ascend_iter1.ThermoXcalibur.opt
    -> Ascend_iter1_1_6.ThermoXcalibur.opt)
  - Normalises line endings to CRLF

Files whose name already contains "_1_6", or whose schema is already <= 1.6,
are skipped. Existing output files are not overwritten unless -Force is set.

The script ONLY removes 1.7+ elements. It does not re-insert 1.6-only
elements (e.g. <collapseMSn>, the split <peakSelectionOptions level="1"/"2">
blocks). The result is a 1.6-tagged file that older Distiller builds parse
leniently; if you need strict 1.6 shape, hand-edit afterwards.

.PARAMETER Path
Directory containing .opt files, or the path to a single .opt file.
Defaults to the standard Distiller processing options folder.

.PARAMETER Filter
Glob filter for input files when -Path is a directory. Default: *.opt

.PARAMETER Force
Overwrite an existing _1_6 output file.

.EXAMPLE
PS> .\downgrade-opt-to-1.6.ps1
Downgrade every .opt file in the default folder.

.EXAMPLE
PS> .\downgrade-opt-to-1.6.ps1 -Filter 'Ascend*.opt'
Only Ascend variants.

.EXAMPLE
PS> .\downgrade-opt-to-1.6.ps1 -Path 'C:\path\to\Custom.ThermoXcalibur.opt' -Force
Single file, overwriting any prior output.
#>
[CmdletBinding()]
param(
  [string]$Path   = 'C:\ProgramData\Matrix Science\Mascot Distiller\processing options',
  [string]$Filter = '*.opt',
  [switch]$Force
)

function Get-OutputName {
  param([string]$InName)
  if ($InName -match '^(.+)(\.[^.]+\.opt)$') {
    return $matches[1] + '_1_6' + $matches[2]
  }
  throw "Cannot derive output name from: $InName (expected '<name>.<vendor>.opt')"
}

function Convert-OptTo16 {
  param([string]$InPath, [string]$OutPath, [switch]$Force)

  if ((Test-Path -LiteralPath $OutPath) -and -not $Force) {
    Write-Host "skip:  $(Split-Path $OutPath -Leaf) already exists (use -Force)"
    return
  }

  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  $text = [IO.File]::ReadAllText($InPath, $utf8NoBom)

  # 1. downgrade schema version
  $text = [regex]::Replace($text, 'minorVersion="\d+"', 'minorVersion="6"')

  # 2. strip elements not present in 1.6 (whole line incl. trailing newline)
  $stripPatterns = @(
    '(?m)^[ \t]*<precursorIonMobilityGroupTol>.*?</precursorIonMobilityGroupTol>\r?\n',
    '(?m)^[ \t]*<vendorOption\b[^>]*\btype="11".*?</vendorOption>\r?\n',
    '(?m)^[ \t]*<vendorOption\b[^>]*\btype="12".*?</vendorOption>\r?\n'
  )
  foreach ($p in $stripPatterns) {
    $text = [regex]::Replace($text, $p, '')
  }

  # 3. normalise line endings to CRLF
  $text = $text.Replace("`r`n", "`n").Replace("`n", "`r`n")

  [IO.File]::WriteAllText($OutPath, $text, $utf8NoBom)
  Write-Host "wrote: $(Split-Path $OutPath -Leaf)"
}

# resolve input files
if (Test-Path -LiteralPath $Path -PathType Container) {
  $files = Get-ChildItem -LiteralPath $Path -Filter $Filter -File
} elseif (Test-Path -LiteralPath $Path -PathType Leaf) {
  $files = @(Get-Item -LiteralPath $Path)
} else {
  throw "Path not found: $Path"
}

foreach ($f in $files) {
  if ($f.Name -like '*_1_6*') {
    Write-Host "skip:  $($f.Name) (already has _1_6 suffix)"
    continue
  }

  $head = Get-Content -LiteralPath $f.FullName -TotalCount 2
  if ($head.Count -lt 2) {
    Write-Host "skip:  $($f.Name) (file too short)"
    continue
  }
  $vMatch = [regex]::Match($head[1], 'minorVersion="(\d+)"')
  if (-not $vMatch.Success) {
    Write-Host "skip:  $($f.Name) (no minorVersion attribute)"
    continue
  }
  $minor = [int]$vMatch.Groups[1].Value
  if ($minor -le 6) {
    Write-Host "skip:  $($f.Name) (already schema 1.$minor)"
    continue
  }

  $outName = Get-OutputName -InName $f.Name
  $outPath = Join-Path $f.Directory.FullName $outName
  Convert-OptTo16 -InPath $f.FullName -OutPath $outPath -Force:$Force
}
