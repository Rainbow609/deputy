# Node Verification

## Purpose
Define how Deputy verifies proxy nodes and records node health signals.

## Requirements

### Requirement: TCP connectivity probing
The system SHALL perform TCP connectivity probing to verify node server and port accessibility.

#### Scenario: Successful TCP connection
- **WHEN** a node's server and port are accessible via TCP
- **THEN** the system marks the node as alive
- **AND** the system records the connection time

#### Scenario: Failed TCP connection
- **WHEN** a node's server and port are not accessible via TCP
- **THEN** the system marks the node as dead
- **AND** the system records the failure reason (timeout, connection refused, etc.)

#### Scenario: Missing endpoint information
- **WHEN** a node configuration lacks server or port information
- **THEN** the system marks the node as dead with reason "missing-endpoint"
- **AND** the system skips further verification for that node

### Requirement: HTTP health checking
The system SHALL perform HTTP health checking to verify node functionality.

#### Scenario: Successful HTTP health check
- **WHEN** a node successfully responds to HTTP health check requests
- **THEN** the system marks the node as healthy
- **AND** the system records the response time

#### Scenario: Failed HTTP health check
- **WHEN** a node fails to respond to HTTP health check requests
- **THEN** the system marks the node as unhealthy
- **AND** the system records the failure reason

#### Scenario: HTTP health check timeout
- **WHEN** HTTP health check exceeds the configured timeout
- **THEN** the system marks the node as unhealthy with reason "timeout"
- **AND** the system continues with other nodes

### Requirement: Latency testing and sorting
The system SHALL measure node latency and sort nodes by latency for optimal user experience.

#### Scenario: Latency measurement
- **WHEN** the system performs latency testing on a node
- **THEN** the system records the round-trip time in milliseconds
- **AND** the system performs multiple measurements for accuracy

#### Scenario: Node sorting by latency
- **WHEN** the system completes latency testing on all nodes
- **THEN** the system sorts nodes by latency in ascending order
- **AND** the system provides the sorted list for configuration generation

#### Scenario: Failed latency measurement
- **WHEN** latency measurement fails for a node
- **THEN** the system assigns a maximum latency value
- **AND** the system places the node at the end of the sorted list

### Requirement: Concurrent verification processing
The system SHALL perform node verification concurrently to optimize processing time.

#### Scenario: Concurrent TCP probing
- **WHEN** the system performs TCP connectivity probing on multiple nodes
- **THEN** the system processes nodes concurrently up to the configured limit
- **AND** the system respects the concurrency limit to avoid resource exhaustion

#### Scenario: Concurrent HTTP health checks
- **WHEN** the system performs HTTP health checks on multiple nodes
- **THEN** the system processes health checks concurrently
- **AND** the system properly handles concurrent failures and successes

#### Scenario: Resource management
- **WHEN** concurrent verification approaches resource limits
- **THEN** the system implements backpressure or queueing
- **AND** the system maintains stability without overwhelming system resources

### Requirement: Verification result aggregation
The system SHALL aggregate verification results from multiple checks into a comprehensive node status.

#### Scenario: All verifications pass
- **WHEN** a node passes TCP, HTTP, and latency verifications
- **THEN** the system marks the node as fully verified
- **AND** the system includes all verification metrics in the final report

#### Scenario: Partial verification failure
- **WHEN** a node fails some but not all verification checks
- **THEN** the system marks the node with appropriate status based on severity
- **AND** the system includes detailed failure information in the report

#### Scenario: All verifications fail
- **WHEN** a node fails all verification checks
- **THEN** the system marks the node as dead
- **AND** the system excludes the node from final configuration output

### Requirement: Verification timeout and retry handling
The system SHALL implement proper timeout and retry mechanisms for verification operations.

#### Scenario: TCP connection timeout
- **WHEN** TCP connection exceeds the configured timeout
- **THEN** the system aborts the connection attempt
- **AND** the system marks the verification as failed

#### Scenario: Configurable retry mechanism
- **WHEN** initial verification attempts fail
- **THEN** the system retries verification according to the configured retry policy
- **AND** the system implements exponential backoff between retries

#### Scenario: Maximum retry limit
- **WHEN** verification attempts reach the maximum retry limit
- **THEN** the system marks the node as failed
- **AND** the system stops further retry attempts for that node
