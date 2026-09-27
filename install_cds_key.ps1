<#
.SYNOPSIS
    Installe la cle API du Climate Data Store sous Windows.

.DESCRIPTION
    Ecrit le fichier `.cdsapirc` attendu par le CDS dans le dossier personnel
    de l'utilisateur, conformement a la procedure documentee par l'ECMWF :
    https://confluence.ecmwf.int/spaces/CKB/pages/121847376/

    La cle s'obtient gratuitement sur https://cds.climate.copernicus.eu/user
    (section « Set up the CDS API personal access token »).

    Le fichier cree contient la cle en clair : a utiliser sur un poste de
    travail, jamais sur une machine partagee.

.PARAMETER Key
    Jeton d acces personnel. Si omis, le script le demande de maniere securisee.

.PARAMETER Url
    Adresse de l'API CDS. Par defaut, le portail actuel.

.PARAMETER Project
    Ecrit le fichier a la racine du projet au lieu du dossier personnel.
    Utile pour equiper une salle de PC a partir d'un seul dossier.

.EXAMPLE
    .\install_cds_key.ps1
    .\install_cds_key.ps1 -Key "abcd-1234:efgh-5678" -Project
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Key,

    [string]$Url = "https://cds.climate.copernicus.eu/api",

    [switch]$Project
)

$ErrorActionPreference = "Stop"

# --- Verification de Python ----------------------------------------------------
try {
    $python = Get-Command python -ErrorAction Stop
} catch {
    Write-Error "Python est introuvable dans le PATH. Installez Python 3.10 ou superieur depuis https://www.python.org/downloads/"
    exit 1
}
Write-Host "Python detecte :" $python.Source

# --- Recuperation de la cle ----------------------------------------------------
if (-not $Key) {
    Write-Host ""
    Write-Host "Pour obtenir votre cle :" -ForegroundColor Cyan
    Write-Host "  1. Connectez-vous sur https://cds.climate.copernicus.eu/user"
    Write-Host "  2. Ouvrez la section 'Set up the CDS API personal access token'"
    Write-Host "  3. Copiez la valeur affichee apres `key:`"
    Write-Host ""
    $secure = Read-Host "Collez votre cle" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $Key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (-not $Key) {
    Write-Error "Aucune cle fournie."
    exit 1
}

# --- Verification du format du jeton ------------------------------------------
# Le CDS attend un jeton d acces personnel : une longue chaine sur une seule
# ligne. Les trois erreurs les plus frequentes sont signalees ici plutot que
# d echec d authentification.
$looksLikeUuidSecret = $Key -match '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}:.+$'

if ($Key -match ':' -and $looksLikeUuidSecret) {
    Write-Warning "Cette cle a l ancien format `identifiant:secret`."
    Write-Warning "Le CDS ne l accepte plus depuis septembre 2024 : il n existe plus"
    Write-Warning "d identifiant utilisateur. Recuperer le jeton d acces personnel sur :"
    Write-Warning "    https://cds.climate.copernicus.eu/user"
    Write-Warning "    (section « Set up the CDS API personal access token »)"
    $answer = Read-Host "Continuer malgre tout ? (o/N)"
    if ($answer -ne "o") { exit 1 }
}
elseif ($Key.Length -lt 20) {
    Write-Warning "Cette valeur est tres courte ($($Key.Length) caracteres)."
    Write-Warning "Le jeton du CDS est une longue chaine. Si vous utilisez le"
    Write-Warning "« Client ID » ou le « Client secret » de votre profil ECMWF : ces"
    Write-Warning "identifiants servent a l API Web ECMWF, PAS au Climate Data Store."
}
elseif ($Key -match '^[\s"]|[\s"]$') {
    Write-Warning "La cle commence ou finit par un espace ou un guillemet."
    Write-Warning "Copiez-la sans ces caracteres."
    $Key = $Key.Trim().Trim('"').Trim("'")
}

# --- Verification de la presence de cdsapi -------------------------------------
$hasCds = & $python.Source -c "import cdsapi" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "La bibliotheque 'cdsapi' est absente. Installation en cours..." -ForegroundColor Yellow
    & $python.Source -m pip install cdsapi
}

# --- Ecriture du fichier -------------------------------------------------------
if ($Project) {
    $target = Join-Path $PSScriptRoot ".cdsapirc"
} else {
    $target = Join-Path $env:USERPROFILE ".cdsapirc"
}

@"
url: $Url
key: $Key
"@ | Set-Content -Path $target -Encoding UTF8

Write-Host ""
Write-Host "Cle ecrite dans : $target" -ForegroundColor Green
Write-Host ""
Write-Host "Verification..." -ForegroundColor Cyan

$report = & $python.Source (Join-Path $PSScriptRoot "verify_install.py") 2>&1
$report | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Termine. Lancez l'application avec :" -ForegroundColor Cyan
Write-Host "    streamlit run app.py"
