/*
# ========================================================================
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

use std::path::PathBuf;
use clap::{Parser, Subcommand};

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

fn main() {
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Build { input, output } => {
            println!("Building: {:?}", input);
            if let Some(out) = output {
                println!("Output: {:?}", out);
            }
            // TODO: Implement build
        }
        Commands::Run { input } => {
            println!("Running: {:?}", input);
            // TODO: Implement run
        }
        Commands::Exec { input } => {
            println!("Executing: {:?}", input);
            // TODO: Implement exec
        }
        Commands::Disasm { input } => {
            println!("Disassembling: {:?}", input);
            // TODO: Implement disasm
        }
    }
}
