# Multi-Platform Configuration Generation

## Purpose
Define how Deputy generates and manages publishable Mihomo configuration outputs.
## Requirements
### Requirement: Template-based configuration generation
The system SHALL use `config.template.yaml` as the single source template for generating `config.yaml`.

#### Scenario: Template variable substitution
- **WHEN** the system processes `config.template.yaml`
- **THEN** the system substitutes node placeholders with data from `nodes.toml` and subscription fetch results
- **AND** the system preserves the static template sections, including http rule-providers and rule definitions

#### Scenario: Single template selection
- **WHEN** the system generates the publishable configuration
- **THEN** the system uses only `config.template.yaml`
- **AND** the system does not require platform-specific template files under `templates/`

### Requirement: Configuration validation
The system SHALL validate the generated `config.yaml` before publication.

#### Scenario: YAML syntax validation
- **WHEN** the system generates `config.yaml`
- **THEN** the system validates YAML syntax for that output file
- **AND** the system reports syntax errors before publication

#### Scenario: Single output validation
- **WHEN** validation completes
- **THEN** the system treats `config.yaml` as the only required publishable configuration artifact
- **AND** the system does not require validation of removed platform-specific outputs

### Requirement: Configuration output management
The system SHALL manage `config.yaml` as the canonical generated configuration output.

#### Scenario: Output file organization
- **WHEN** the system writes generated configuration
- **THEN** the system writes the publishable file as `config.yaml`
- **AND** the system makes that artifact available through the release pipeline

#### Scenario: Output file consistency
- **WHEN** generating `config.yaml`
- **THEN** the system keeps node ordering and rendered template sections deterministic
- **AND** the system avoids creating legacy platform-specific configuration files

### Requirement: Single pipeline configuration generation
The system SHALL generate one publishable Mihomo configuration through the `nodes.toml` to `config.yaml` pipeline.

#### Scenario: Single output generation
- **WHEN** the scheduled sync pipeline runs
- **THEN** the system renders one `config.yaml` output
- **AND** the system does not generate desktop, mobile, baipiao, or magisk variant files

#### Scenario: Shared node data
- **WHEN** generating `config.yaml`
- **THEN** the system uses the shared node data from `nodes.toml` and configured subscription sources
- **AND** the system applies one consistent transformation for all consumers
