/*
========================================================================
Copyright (C) 2026 Nexa-Language
This file is part of Nexa Project.

Nexa is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Nexa is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
========================================================================
*/
//! Nexa AVM Command Line Interface

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use clap::{Parser, Subcommand};
use nexa_avm::bytecode::{BytecodeCompiler, BytecodeModule};
use nexa_avm::compiler::Parser as NexaParser;
use nexa_avm::vm::{ExecutionResult, Interpreter, InterpreterConfig};

#[derive(Parser)]
#[command(name = "avm")]
#[command(about = "Nexa Agent Virtual Machine", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Compile a Nexa source file to bytecode
    Build {
        /// Input .nx file
        #[arg(short, long)]
        input: PathBuf,
        /// Output .nxc file
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
    /// Run a compiled bytecode file
    Run {
        /// Input .nxc file
        input: PathBuf,
    },
    /// Compile and run a Nexa source file
    Exec {
        /// Input .nx file
        input: PathBuf,
    },
    /// Disassemble a bytecode file
    Disasm {
        /// Input .nxc file
        input: PathBuf,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Build { input, output } => {
            let module = compile_file(&input)?;
            let output_path = output.unwrap_or_else(|| default_output_path(&input));
            write_module(&output_path, &module)?;
            println!("Built {} -> {}", input.display(), output_path.display());
        }
        Commands::Run { input } => {
            let module = read_module(&input)?;
            let result = run_module(module)?;
            print_execution_result(&result);
        }
        Commands::Exec { input } => {
            let module = compile_file(&input)?;
            let result = run_module(module)?;
            print_execution_result(&result);
        }
        Commands::Disasm { input } => {
            let module = read_module(&input)?;
            print!("{}", disassemble_module(&module));
        }
    }

    Ok(())
}

fn compile_file(input: &Path) -> Result<BytecodeModule> {
    let source = fs::read_to_string(input)
        .with_context(|| format!("failed to read Nexa source: {}", input.display()))?;
    let module_name = input
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("main")
        .to_string();
    compile_source(&source, module_name, Some(input.display().to_string()))
}

fn compile_source(
    source: &str,
    module_name: String,
    source_file: Option<String>,
) -> Result<BytecodeModule> {
    let program =
        NexaParser::parse_from_source(source).map_err(|e| anyhow!("parse failed: {e}"))?;
    let mut module = BytecodeCompiler::new(module_name)
        .compile(&program)
        .map_err(|e| anyhow!("compile failed: {e}"))?;
    module.metadata.source_file = source_file;
    Ok(module)
}

fn read_module(input: &Path) -> Result<BytecodeModule> {
    let bytes = fs::read(input)
        .with_context(|| format!("failed to read bytecode module: {}", input.display()))?;
    BytecodeModule::from_bytes(&bytes).map_err(|e| {
        anyhow!(
            "failed to decode bytecode module '{}': {e}",
            input.display()
        )
    })
}

fn write_module(output: &Path, module: &BytecodeModule) -> Result<()> {
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).with_context(|| {
                format!("failed to create output directory: {}", parent.display())
            })?;
        }
    }
    let bytes = module
        .to_bytes()
        .map_err(|e| anyhow!("failed to encode bytecode module: {e}"))?;
    fs::write(output, bytes)
        .with_context(|| format!("failed to write bytecode module: {}", output.display()))
}

fn run_module(module: BytecodeModule) -> Result<ExecutionResult> {
    let mut interpreter = Interpreter::new(InterpreterConfig::default());
    interpreter.load_module(module);
    interpreter
        .run()
        .map_err(|e| anyhow!("runtime failed: {e}"))
}

fn default_output_path(input: &Path) -> PathBuf {
    input.with_extension("nxc")
}

fn print_execution_result(result: &ExecutionResult) {
    println!("Result: {:?}", result.value);
    println!("Instructions executed: {}", result.instructions_executed);
}

fn disassemble_module(module: &BytecodeModule) -> String {
    let mut out = String::new();
    out.push_str(&format!("Module: {}\n", module.name));
    out.push_str(&format!("Version: {}\n", module.version));
    out.push_str(&format!("Entry point: {}\n", module.entry_point));
    out.push_str(&format!("Compiler: {}\n", module.metadata.compiler_version));
    if let Some(source_file) = &module.metadata.source_file {
        out.push_str(&format!("Source: {}\n", source_file));
    }

    out.push_str("\nConstants:\n");
    for (idx, constant) in module.constants.iter().enumerate() {
        out.push_str(&format!("  [{idx}] {:?}\n", constant));
    }

    out.push_str("\nSymbols:\n");
    for (idx, symbol) in module.symbols.iter().enumerate() {
        out.push_str(&format!("  [{idx}] {symbol}\n"));
    }

    out.push_str("\nInstructions:\n");
    for (idx, instruction) in module.instructions.iter().enumerate() {
        out.push_str(&format!(
            "  {idx:04}: {:?} {:?}",
            instruction.opcode, instruction.operand
        ));
        if let Some(location) = &instruction.source_location {
            out.push_str(&format!(" @ {}:{}", location.line, location.column));
        }
        out.push('\n');
    }

    out
}
