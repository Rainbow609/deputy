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
- **AND** the system supports regional placeholders ``{HK_LIST}`` / ``{JP_LIST}`` / ``{US_LIST}`` / ``{SG_LIST}`` / ``{TW_LIST}`` populated from the rendered proxy names that match each region's regex
- **AND** the system computes those regional placeholders during rendering, producing concrete proxy-name lists rather than client-side ``include-all`` / ``filter`` rules
- **AND** the system preserves YAML anchor declarations (``&pr``) and merge keys (``<<: *pr``) verbatim so that PyYAML and mihomo resolve the shared proxy list across select sub-groups
- **AND** the system preserves any top-level static YAML anchor blocks such as ``p: &p`` verbatim, without requiring the renderer to apply those anchors programmatically
- **AND** the system prefixes ``{NODE_SELECT_LIST}`` with ``自动选择, `` so the ``节点选择`` select group exposes the ``自动选择`` url-test option as a child
- **AND** the system falls back to ``DIRECT`` for any regional placeholder whose bucket is empty

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
