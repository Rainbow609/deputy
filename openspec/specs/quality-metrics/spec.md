# Quality Metrics

## Purpose
Define how Deputy calculates and reports node quality and release metrics.

## Requirements

### Requirement: Node survival rate calculation
The system SHALL calculate and report node survival rates.

#### Scenario: Overall survival rate
- **WHEN** the system completes node verification
- **THEN** the system calculates the percentage of nodes that passed verification
- **AND** the system reports the survival rate in the final statistics

#### Scenario: Per-source survival rate
- **WHEN** the system processes nodes from multiple sources
- **THEN** the system calculates survival rate for each source independently
- **AND** the system reports source-specific survival rates

### Requirement: Regional distribution analysis
The system SHALL analyze and report regional distribution of nodes.

#### Scenario: Regional node counting
- **WHEN** the system processes verified nodes
- **THEN** the system categorizes nodes by geographic region
- **AND** the system reports node count per region

#### Scenario: Regional survival analysis
- **WHEN** the system completes node verification
- **THEN** the system reports survival rate by region
- **AND** the system identifies regions with high or low node quality

### Requirement: Latency statistics generation
The system SHALL generate comprehensive latency statistics for verified nodes.

#### Scenario: Average latency calculation
- **WHEN** the system completes latency testing
- **THEN** the system calculates average latency across all verified nodes
- **AND** the system reports average latency in milliseconds

#### Scenario: Latency distribution
- **WHEN** the system has latency data for multiple nodes
- **THEN** the system generates latency distribution data
- **AND** the system reports percentiles (25th, 50th, 75th, 95th)

#### Scenario: Extremes identification
- **WHEN** analyzing latency data
- **THEN** the system identifies fastest and slowest nodes
- **AND** the system reports extreme values with node identifiers

### Requirement: Node quality scoring
The system SHALL calculate quality scores for individual nodes.

#### Scenario: Quality score calculation
- **WHEN** the system evaluates a node
- **THEN** the system calculates a quality score based on verification results
- **AND** the system considers TCP connectivity, HTTP health, and latency

#### Scenario: Quality score categories
- **WHEN** the system calculates quality scores
- **THEN** the system categorizes nodes into quality tiers (excellent, good, fair, poor)
- **AND** the system reports quality distribution

### Requirement: Change tracking and reporting
The system SHALL track and report changes between verification runs.

#### Scenario: New nodes identification
- **WHEN** comparing current verification results with previous run
- **THEN** the system identifies newly added nodes
- **AND** the system reports count and details of new nodes

#### Scenario: Failed nodes identification
- **WHEN** comparing current verification results with previous run
- **THEN** the system identifies nodes that failed verification
- **AND** the system reports count and failure reasons for failed nodes

#### Scenario: Node performance changes
- **WHEN** comparing latency data between runs
- **THEN** the system identifies significant performance changes
- **AND** the system reports nodes with improved or degraded performance

### Requirement: Statistics formatting and output
The system SHALL format and output quality metrics in a user-friendly manner.

#### Scenario: Console output formatting
- **WHEN** the system outputs statistics to console
- **THEN** the system uses clear formatting with appropriate indentation and spacing
- **AND** the system highlights important metrics

#### Scenario: JSON output for integration
- **WHEN** the system outputs statistics for machine processing
- **THEN** the system provides JSON formatted output
- **AND** the system includes all metrics in structured format

#### Scenario: Release notes integration
- **WHEN** the system generates release notes
- **THEN** the system incorporates quality metrics into release notes
- **AND** the system presents metrics in human-readable format

### Requirement: Historical data tracking
The system SHALL maintain historical quality data for trend analysis.

#### Scenario: Historical data storage
- **WHEN** the system completes a verification run
- **THEN** the system stores quality metrics with timestamp
- **AND** the system maintains configurable history retention

#### Scenario: Trend analysis
- **WHEN** historical data is available
- **THEN** the system can identify quality trends over time
- **AND** the system reports significant changes in quality metrics

### Requirement: Alert threshold management
The system SHALL support configurable alert thresholds for quality metrics.

#### Scenario: Survival rate threshold
- **WHEN** node survival rate falls below configured threshold
- **THEN** the system generates an alert
- **AND** the system includes specific survival rate data in alert

#### Scenario: Latency threshold
- **WHEN** average latency exceeds configured threshold
- **THEN** the system generates an alert
- **AND** the system includes latency data in alert

#### Scenario: Custom alert configuration
- **WHEN** administrators configure custom alert thresholds
- **THEN** the system applies custom thresholds for specific metrics
- **AND** the system respects threshold changes in subsequent runs
