# guild-site-cli Specification

## Purpose
TBD - created by archiving change add-guild-site-cli-crud. Update Purpose after archive.
## Requirements
### Requirement: Create website guild records from an external CLI

The system SHALL provide an external CLI command that creates a website guild
record in the shared database using a unique slug, unique subdomain, and
display name. The CLI MUST support optional clan tags, optional Discord guild
id linkage, and an explicit active/inactive state, defaulting to active when no
state is provided.

#### Scenario: Create an active guild with clan tags

- **WHEN** an operator creates a guild with a valid slug, subdomain, display
  name, and clan tags
- **THEN** the system persists the guild record and its clan tags as a website
  guild site

#### Scenario: Reject duplicate guild identity

- **WHEN** an operator creates a guild whose slug, subdomain, or Discord guild
  id already belongs to another guild
- **THEN** the CLI fails instead of creating a conflicting guild record

### Requirement: List and inspect website guild records

The system SHALL provide external CLI commands to list website guild records
and inspect a single guild record. The CLI output MUST include enough data to
identify the guild, including slug, subdomain, display name, active state, and
configured clan tags.

#### Scenario: List all website guilds

- **WHEN** an operator runs the list command
- **THEN** the CLI returns all website guild records with their identity and
  active state

#### Scenario: Inspect one website guild

- **WHEN** an operator requests one existing guild by selector
- **THEN** the CLI returns that guild's stored website identity and clan tag
  configuration

### Requirement: Update website guild records

The system SHALL provide an external CLI command to update an existing website
guild record. The CLI MUST support changing slug, subdomain, display name,
optional Discord guild id linkage, active state, and clan tags. When clan tags
are provided in an update command, the supplied set SHALL replace the stored
guild clan tags for that guild.

#### Scenario: Update guild identity fields

- **WHEN** an operator updates an existing guild's display name or subdomain
- **THEN** the system persists the new values on the existing guild record

#### Scenario: Replace guild clan tags

- **WHEN** an operator updates a guild and supplies a new clan tag list
- **THEN** the system replaces the previous stored clan tags with the supplied
  set

### Requirement: Deactivate website guild records without deleting them

The system SHALL provide an external CLI command to deactivate a website guild
record without deleting its stored guild-scoped data. The system SHALL also
allow reactivating the same guild record later.

#### Scenario: Deactivate a guild site

- **WHEN** an operator deactivates an existing guild
- **THEN** the guild remains stored but is marked inactive for website
  resolution

#### Scenario: Reactivate a guild site

- **WHEN** an operator reactivates a previously inactive guild
- **THEN** the guild becomes active again without recreating its record

### Requirement: Delete website guild records with explicit confirmation

The system SHALL provide an external CLI command to permanently delete a
website guild record only when explicit confirmation is supplied. Guild-scoped
records owned by that guild SHALL be deleted with it, while global shared
records not owned by the guild, such as site users and players, SHALL remain.

#### Scenario: Delete requires confirmation

- **WHEN** an operator runs the delete command without explicit confirmation
- **THEN** the CLI refuses to delete the guild

#### Scenario: Confirmed guild deletion

- **WHEN** an operator deletes a guild with explicit confirmation
- **THEN** the system removes the guild and its guild-scoped website records
  while preserving unrelated global shared records

