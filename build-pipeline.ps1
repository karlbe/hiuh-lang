# build-pipeline.ps1 — Compile tokenizer/parser and generate executable
# Usage: .\build-pipeline.ps1 [target] [input-file]
# Examples:
#   .\build-pipeline.ps1 parser2          # Generate parser2.exe from hiuh-parser.hiuh
#   .\build-pipeline.ps1 tokenizer2       # Generate tokenizer2.exe from hiuh-tokenizer.hiuh
#   .\build-pipeline.ps1 parser2 test\test-func-main-order.hiuh
#                                         # Test parser2 with a specific file

param(
    [string]$target = "parser2",
    [string]$inputFile = "",
    [switch]$debug = $false
)

$ErrorActionPreference = "Stop"

function Write-Stage {
    param([string]$message)
    Write-Host "`n" -NoNewline
    Write-Host "═" * 80 -ForegroundColor Cyan
    Write-Host "║ $message" -ForegroundColor Cyan
    Write-Host "═" * 80 -ForegroundColor Cyan
}

function Write-Success {
    param([string]$message)
    Write-Host "  ✓ $message" -ForegroundColor Green
}

function Write-Info {
    param([string]$message)
    Write-Host "  → $message" -ForegroundColor Gray
}

function Write-Error {
    param([string]$message)
    Write-Host "  ✗ $message" -ForegroundColor Red
}

function Write-Command {
    param([string]$cmd)
    Write-Host "  CMD: $cmd" -ForegroundColor Yellow
}

# Determine source file based on target
$sourceFile = if ($target -eq "tokenizer2") {
    "src\hiuh-tokenizer.hiuh"
} else {
    "src\hiuh-parser.hiuh"
}

if (-not (Test-Path $sourceFile)) {
    Write-Error "Source file not found: $sourceFile"
    exit 1
}

Write-Host "Building $target from $sourceFile`n"

try {
    # Step 1: Compile tokenizer with Python compiler (always needed)
    Write-Stage "STEP 1: Compile hiuh-tokenizer.hiuh with Python compiler"
    Write-Command "python compiler/hiuh-native.py src/hiuh-tokenizer.hiuh hiuh-tokenizer.exe"
    Write-Info "Input: src/hiuh-tokenizer.hiuh"

    $output = python compiler/hiuh-native.py src/hiuh-tokenizer.hiuh hiuh-tokenizer.exe 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tokenizer compilation FAILED"
        Write-Host $output -ForegroundColor Red
        exit 1
    }

    if (Test-Path hiuh-tokenizer.exe) {
        $tokenizer_size = (Get-Item hiuh-tokenizer.exe).Length
        Write-Success "hiuh-tokenizer.exe created ($tokenizer_size bytes)"
    } else {
        Write-Error "hiuh-tokenizer.exe was not created"
        exit 1
    }

    # Step 2: Compile parser with Python compiler (always needed)
    Write-Stage "STEP 2: Compile hiuh-parser.hiuh with Python compiler"
    Write-Command "python compiler/hiuh-native.py src/hiuh-parser.hiuh hiuh-parser.exe"
    Write-Info "Input: src/hiuh-parser.hiuh"

    $output = python compiler/hiuh-native.py src/hiuh-parser.hiuh hiuh-parser.exe 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Parser compilation FAILED"
        Write-Host $output -ForegroundColor Red
        exit 1
    }

    if (Test-Path hiuh-parser.exe) {
        $parser_size = (Get-Item hiuh-parser.exe).Length
        Write-Success "hiuh-parser.exe created ($parser_size bytes)"
    } else {
        Write-Error "hiuh-parser.exe was not created"
        exit 1
    }

    # Step 3: Run pipeline
    Write-Stage "STEP 3: Run tokenizer → parser pipeline"
    $asmFile = "$target.s"

    if ($inputFile -and (Test-Path $inputFile)) {
        $sourceToProcess = $inputFile
        Write-Info "Processing: $inputFile"
    } else {
        $sourceToProcess = $sourceFile
        Write-Info "Processing: $sourceFile (default source for target)"
    }

    Write-Command ".\hiuh-tokenizer.exe < $sourceToProcess | .\hiuh-parser.exe > $asmFile"

    # Run the pipeline and capture any errors
    $pipelineCmd = ".\hiuh-tokenizer.exe < $sourceToProcess | .\hiuh-parser.exe > $asmFile"
    cmd /c $pipelineCmd 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pipeline execution FAILED with exit code $LASTEXITCODE"
        exit 1
    }

    if (Test-Path $asmFile) {
        $asmSize = (Get-Item $asmFile).Length
        Write-Success "Pipeline completed: $asmFile generated ($asmSize bytes)"
        Write-Info "First 5 lines:"
        Get-Content $asmFile | Select-Object -First 5 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
    } else {
        Write-Error "Output file $asmFile was not created"
        exit 1
    }

    # Step 4: Assemble
    Write-Stage "STEP 4: Assemble with GNU as"
    $objFile = "$target.o"
    Write-Command "G:\msys64\mingw64\bin\as.exe -o $objFile $asmFile"
    Write-Info "Input:  $asmFile ($asmSize bytes)"

    $output = G:\msys64\mingw64\bin\as.exe -o $objFile $asmFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Assembly FAILED"
        Write-Host "=== AS OUTPUT ===" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
        exit 1
    }

    if (Test-Path $objFile) {
        $objSize = (Get-Item $objFile).Length
        Write-Success "Object file created: $objFile ($objSize bytes)"
    } else {
        Write-Error "Object file $objFile was not created"
        exit 1
    }

    # Step 5: Link
    Write-Stage "STEP 5: Link with GNU ld"
    $exeFile = "$target.exe"
    Write-Command "G:\msys64\mingw64\bin\ld.exe -o $exeFile $objFile -lmingw32 -lmsvcrt -lkernel32"
    Write-Info "Input: $objFile ($objSize bytes)"

    $output = G:\msys64\mingw64\bin\ld.exe -o $exeFile $objFile -lmingw32 -lmsvcrt -lkernel32 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Linking FAILED"
        Write-Host "=== LD OUTPUT ===" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
        exit 1
    }

    if (Test-Path $exeFile) {
        $exeSize = (Get-Item $exeFile).Length
        Write-Success "Executable created: $exeFile ($exeSize bytes)"
    } else {
        Write-Error "Executable $exeFile was not created"
        exit 1
    }

    # Step 6: Run if input file specified
    if ($inputFile -and (Test-Path $inputFile)) {
        Write-Stage "STEP 6: Test $exeFile"

        if ($debug) {
            Write-Info "Running under GDB debugger for diagnostics"
            Write-Command "echo 'run < $inputFile' | gdb .\$exeFile"

            # Create a GDB command file for automated debugging
            $gdbCommands = @"
set logging on
set logging file gdb-output.txt
set logging overwrite on
handle SIGSEGV nostop noprint pass
run < $inputFile
backtrace
info registers
quit
"@
            $gdbCommands | Out-File -Encoding UTF8 gdb-commands.txt

            Write-Info "GDB commands saved to gdb-commands.txt"
            Write-Info "Running: gdb --batch -x gdb-commands.txt .\$exeFile < $inputFile"

            cmd /c "gdb --batch -x gdb-commands.txt .\$exeFile < $inputFile" 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

            if (Test-Path gdb-output.txt) {
                Write-Info "GDB output saved to gdb-output.txt"
                Write-Host "`n=== GDB OUTPUT ===" -ForegroundColor Yellow
                Get-Content gdb-output.txt | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
            }

            Write-Error "✗ Debugging complete - review gdb-output.txt for error details"
            exit 1
        } else {
            Write-Command ".\hiuh-tokenizer.exe < $inputFile | .\$exeFile > test-output.s"
            Write-Info "Running: $exeFile"
            Write-Info "Use -debug flag to run under GDB for detailed error info"

            cmd /c ".\hiuh-tokenizer.exe < $inputFile | .\$exeFile > test-output.s" 2>&1
            $exitCode = $LASTEXITCODE

            if ($exitCode -eq 0) {
                Write-Success "✓ Test PASSED (exit code 0)"
                if (Test-Path test-output.s) {
                    $outputSize = (Get-Item test-output.s).Length
                    Write-Info "Generated test-output.s ($outputSize bytes)"
                }
            } else {
                Write-Error "✗ Test FAILED with exit code $exitCode"
                if ($exitCode -eq -1073741819) {
                    Write-Error "This is an access violation (STATUS_ACCESS_VIOLATION)"
                    Write-Error "Executable crashed while trying to execute generated code"
                    Write-Error "Run with -debug flag: .\build-pipeline.ps1 $target $inputFile -debug"
                }
                exit 1
            }
        }
    } else {
        Write-Host "`n" -NoNewline
        Write-Host "═" * 80 -ForegroundColor Green
        Write-Host "║ BUILD COMPLETE" -ForegroundColor Green
        Write-Host "═" * 80 -ForegroundColor Green
        Write-Success "Executable ready: $exeFile"
        Write-Info "Next: Run manual test or use -inputFile parameter to test"
    }

} catch {
    Write-Error $_
    exit 1
}
