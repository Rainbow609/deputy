# TOML Node Configuration

## ADDED Requirements

### Requirement: Parse TOML configuration file
The system SHALL parse a TOML configuration file that contains both static nodes and subscription sources.

#### Scenario: Valid TOML configuration file
- **WHEN** the system reads a valid `nodes.toml` file
- **THEN** the system successfully parses static nodes and subscription sources
- **AND** the system extracts all configuration parameters

#### Scenario: Invalid TOML syntax
- **WHEN** the TOML file contains syntax errors
- **THEN** the system reports a clear error message indicating the line and position of the error
- **AND** the system terminates with a non-zero exit code

### Requirement: Support static node configuration
The system SHALL support static node configuration in TOML format for various proxy types.

#### Scenario: VMess static node
- **WHEN** the TOML file contains a VMess static node configuration
- **THEN** the system correctly parses the node including server, port, UUID, cipher, and other required fields
- **AND** the system validates all required fields are present

#### Scenario: Shadowsocks static node
- **WHEN** the TOML file contains a Shadowsocks static node configuration
- **THEN** the system correctly parses the node including server, port, password, and cipher
- **AND** the system validates all required fields are present

#### Scenario: Missing required fields
- **WHEN** a static node configuration is missing required fields
- **THEN** the system reports which fields are missing
- **AND** the system skips that node with a warning message

### Requirement: Support subscription source configuration
The system SHALL support subscription source configuration with URL and optional metadata.

#### Scenario: Single subscription source
- **WHEN** the TOML file contains a subscription source with a valid URL
- **THEN** the system successfully fetches and parses the subscription
- **AND** the system applies any specified prefix or filters

#### Scenario: Multiple subscription sources
- **WHEN** the TOML file contains multiple subscription sources
- **THEN** the system processes each subscription source in parallel
- **AND** the system merges nodes from all sources with proper naming to avoid conflicts

#### Scenario: Invalid subscription URL
- **WHEN** a subscription source URL is invalid or unreachable
- **THEN** the system reports the error and continues processing other sources
- **AND** the system marks the failed source in the final report

### Requirement: Configuration validation
The system SHALL validate the TOML configuration structure and content before processing.

#### Scenario: Valid configuration structure
- **WHEN** the TOML configuration follows the expected structure
- **THEN** the system proceeds with node processing
- **AND** all configuration parameters are applied correctly

#### Scenario: Unknown configuration keys
- **WHEN** the TOML file contains unknown configuration keys
- **THEN** the system warns about the unknown keys
- **AND** the system continues processing with known configuration

#### Scenario: Invalid configuration values
- **WHEN** configuration values have invalid types or ranges
- **THEN** the system reports the specific validation error
- **AND** the system uses safe default values where applicable

### Requirement: Mixed static and subscription nodes
The system SHALL support mixing static nodes and subscription nodes in the same configuration.

#### Scenario: Combined configuration
- **WHEN** the TOML file contains both static nodes and subscription sources
- **THEN** the system processes static nodes and subscription nodes together
- **AND** the system merges them into a unified node list
- **AND** the system applies consistent naming and validation to all nodes

#### Scenario: Node name conflicts
- **WHEN** static nodes and subscription nodes have conflicting names
- **THEN** the system applies automatic prefixing or renaming to resolve conflicts
- **AND** the system preserves the identity of each node source