# Getting Started

## Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yuktakul04/CS-GY-9223-Open-Source.git
   cd CS-GY-9223-Open-Source
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Install development dependencies:
   ```bash
   uv sync --all-extras
   ```

## Running Tests

```bash
uv run pytest
```

## Building Documentation

```bash
uv run mkdocs serve
```
