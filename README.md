# CalmAI

A comprehensive mental health support system leveraging retrieval-augmented generation for personalized therapy assistance.

## Table of Contents

- [Overview](#overview)
- [Folder Structure](#folder-structure)
- [Installation](#installation)
- [Contributing](#contributing)
- [Documentation](#documentation)

## Overview

This project implements a mental health support platform that combines embedding models with retrieval-augmented generation to provide personalized therapy assistance. The system includes a therapist dashboard and patient journaling interface.

## Folder Structure

The repository is organized to separate concerns clearly. The root` directory contains all source code, subdivided into:

- **`data/`** - Data loading and preprocessing scripts
- **`models/`** - Embedding model training and evaluation code
- **`backend/`** - Backend service code for handling requests and business logic
- **`frontend/`** - Therapist dashboard and patient journaling interfaces
- **`logs/`** - contains all the application logs
- **`assets/`** - contains all the static assests to be consumed by the applications

The **`notebooks/`** directory contains Jupyter notebooks for exploratory data analysis, model experimentation, and result visualization. These notebooks are primarily for development and are not part of the production pipeline.

The **`pipelines/`** directory contains DVC pipeline definitions and Airflow DAGs for orchestrating data processing, model training, and deployment workflows.

The **`infrastructure/`** directory contains Terraform or CloudFormation templates for provisioning cloud resources, along with Kubernetes manifests for container orchestration.

The **`docs/`** directory contains project documentation including backend specifications, architecture diagrams, and user guides.

## Installation

### Prerequisites

- Python 3.8 or higher
- pip or conda package manager
- Docker (optional, for containerized deployment)

### Setup

1. **Clone the repository:**
```bash
   git clone <repository-url>
   cd <repository-name>
```

## Contributing

We welcome contributions! Please follow these guidelines:

1. Create a feature branch from `main` (`git checkout -b feature/your-feature`)
2. Commit your changes (`git commit -m 'Add some feature'`)
3. Push to the branch (`git push origin feature/your-feature`)
4. Open a Pull Request to merge into `main`

Please ensure:
- Code follows the project's style guidelines
- Documentation is updated for new features