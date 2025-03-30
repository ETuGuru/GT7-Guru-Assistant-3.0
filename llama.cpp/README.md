# llama.cpp Integration

This directory contains the llama.cpp library integration for running the Gemma model.

## Setup
1. Clone llama.cpp repository
2. Build the library following installation instructions
3. Copy necessary files to this directory

## Configuration
The library is configured to work with:
- Gemma 3B model
- 4-bit quantization
- CPU inference

Note: Binary files and build artifacts are ignored by Git.

# llama.cpp Integration

This directory contains the llama.cpp implementation for the project.

## Building llama.cpp

1. Clone the llama.cpp repository:
   `ash
   git clone https://github.com/ggerganov/llama.cpp.git
   cd llama.cpp
   `

2. Build the project:
   `ash
   cmake -B build
   cmake --build build --config Release
   `

3. Verify the installation by running the included examples

## Configuration

- Ensure BLAS is properly configured for optimal performance
- Check CPU compatibility for specific optimizations
- Follow the official llama.cpp documentation for detailed setup instructions

## Troubleshooting

- Refer to the official repository for common issues and solutions
- Check system requirements and dependencies
- Verify build configurations match your system architecture
