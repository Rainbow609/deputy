# GitHub Releases Distribution

## ADDED Requirements

### Requirement: GitHub Release creation
The system SHALL create GitHub Releases for publishing configuration files.

#### Scenario: Create new release
- **WHEN** the system has new configuration files to publish
- **THEN** the system creates a new GitHub Release
- **AND** the system uses timestamp-based version naming

#### Scenario: Release with configuration files
- **WHEN** creating a GitHub Release
- **THEN** the system attaches the single generated configuration file (config.yaml)
- **AND** the system includes comprehensive release notes

#### Scenario: Single configuration file publication
- **WHEN** the system creates a GitHub Release
- **THEN** the system publishes only one configuration file (config.yaml)
- **AND** the system does not create multiple platform-specific files
- **AND** the single config.yaml is suitable for various platforms (desktop, mobile, Magisk)

### Requirement: Timestamp-based versioning
The system SHALL use timestamp-based versioning for GitHub Releases.

#### Scenario: Version naming format
- **WHEN** the system creates a new release
- **THEN** the system uses format `vYYYY-MM-DD-HHMMSS` for version naming
- **AND** the system uses UTC timezone for timestamp generation

#### Scenario: Version uniqueness
- **WHEN** creating multiple releases in quick succession
- **THEN** each version name is unique based on exact timestamp
- **AND** the system ensures no duplicate version names

### Requirement: Conditional release creation
The system SHALL only create releases when there are actual configuration changes.

#### Scenario: No configuration changes
- **WHEN** the system runs but configuration files have no changes
- **THEN** the system does not create a new release
- **AND** the system logs that no changes were detected

#### Scenario: Configuration changes detected
- **WHEN** the system detects changes in configuration files
- **THEN** the system creates a new release with updated files
- **AND** the system includes change information in release notes

### Requirement: Release notes generation
The system SHALL generate comprehensive release notes for each release.

#### Scenario: Node statistics
- **WHEN** generating release notes
- **THEN** the system includes total node count
- **AND** the system includes regional distribution statistics
- **AND** the system includes node survival rate

#### Scenario: Latency statistics
- **WHEN** generating release notes
- **THEN** the system includes average latency
- **AND** the system includes fastest and slowest node information
- **AND** the system includes latency distribution data

#### Scenario: Change documentation
- **WHEN** generating release notes
- **THEN** the system includes new nodes added
- **AND** the system includes failed nodes removed
- **AND** the system includes configuration changes

### Requirement: Multi-file release attachment
The system SHALL attach multiple configuration files to each release.

#### Scenario: All platform configurations
- **WHEN** creating a release
- **THEN** the system attaches desktop, mobile, and Magisk configuration files
- **AND** each file is named appropriately for its platform

#### Scenario: Additional metadata files
- **WHEN** creating a release
- **THEN** the system may attach additional metadata files
- **AND** the system includes file descriptions in release notes

### Requirement: GitHub Actions integration
The system SHALL integrate with GitHub Actions for automated release creation.

#### Scenario: Automated release workflow
- **WHEN** the GitHub Actions workflow triggers
- **THEN** the system runs the complete verification and generation process
- **AND** the system automatically creates releases when changes are detected

#### Scenario: Workflow permissions
- **WHEN** the GitHub Actions workflow runs
- **THEN** the system has necessary permissions to create releases
- **AND** the system handles permission errors appropriately

### Requirement: Release failure handling
The system SHALL handle release creation failures gracefully.

#### Scenario: Release creation failure
- **WHEN** release creation fails due to API or network issues
- **THEN** the system logs the failure with detailed error information
- **AND** the system does not leave the system in inconsistent state

#### Scenario: Partial failure handling
- **WHEN** some files fail to attach but release creation succeeds
- **THEN** the system includes warning in release notes
- **AND** the system ensures partial releases are clearly marked

### Requirement: Release history management
The system SHALL maintain proper release history and management.

#### Scenario: Release listing
- **WHEN** users query available releases
- **THEN** the system provides access to release history
- **AND** each release includes version, date, and change summary

#### Scenario: Latest release identification
- **WHEN** users request the latest configuration
- **THEN** the system identifies and provides the most recent release
- **AND** the system ensures latest release points to stable configuration