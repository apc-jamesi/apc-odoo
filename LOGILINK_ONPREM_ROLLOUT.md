# Logilink On-Prem Rollout Guide

This guide explains how to use your current Windows PC as a temporary on-prem Odoo server for `apc_logilink`, then later move the same setup to a dedicated server.

## Scope

This guide is for:

- Odoo running from this repo: `C:\Users\APC - James\Documents\GitHub\apc-odoo`
- Custom module: `custom\apc_logilink`
- Local PC acting as the Odoo server on your Wi-Fi/LAN
- Other users opening Odoo from another PC on the same network

This guide does not change code. It is an operational checklist.

## Current Setup Summary

- Odoo source in this repo is Community-based
- Odoo version in codebase: `19.0`
- Main config file: `odoo.conf`
- Current custom addon path already includes:
  - `custom_addons`
  - `custom`
- `Logilink` module folder:
  - `custom\apc_logilink`

## Goal

Use your current machine as a temporary server so that:

- you create and manage the database yourself
- users connect from other PCs using your machine's LAN IP
- users go to the login page and use Logilink
- users do not manage databases themselves

## Phase 1: Prepare the Server PC

### 1. Confirm the host machine

Pick one machine to act as the Odoo server.

That machine must:

- have this repo
- have PostgreSQL running
- have Python environment/dependencies working
- be reachable by other PCs on the same network

### 2. Keep the host machine on a stable network

For the most stable result:

- use LAN on the server PC if possible
- avoid changing Wi-Fi networks during testing
- make sure the server PC does not sleep automatically

### 3. Confirm Odoo starts locally

Before testing with other PCs, verify on the server PC that:

- Odoo starts successfully
- `http://localhost:8069` opens
- you can reach the database screen or login page

## Phase 2: Create the First Database Yourself

### 1. Create the database only from the server PC

Do this yourself first. Do not ask users to do it.

At the database creation page:

- set a strong master password
- create the intended database name
- create the first administrator account

Recommended example naming:

- Database name: `apc_logilink_prod`
- Admin email: use your official admin email

Important:

- keep the master password private
- do not send the master password to users
- if a generated master password was shown publicly before, replace it with a new one

### 2. Log in as administrator

After database creation:

- log in as the admin user
- finish the initial onboarding

## Phase 3: Install Logilink

### 1. Update the apps list

In Odoo:

- go to `Apps`
- use `Update Apps List`

### 2. Install the module

Search for:

- `Logilink - Asset Registry System`

Then:

- click `Install`

### 3. Verify the menus

After install, confirm the `Logilink` menu appears with at least:

- `Asset Registry`
- `Asset Borrowing / Asset Assignment`
- `Purchase Request`
- `Purchase Order`
- `Goods Receipt Note (GRN)`
- `Supplier Invoice`
- `Payment`
- `Suppliers`
- `Community`
- `Department`

## Phase 4: Prepare User Access

### 1. Create users

Before other people connect:

- create the user accounts they will use
- assign the correct access rights
- test at least one non-admin user login

### 2. Configure company basics

Before broader use, set at least:

- company name
- logo
- language
- timezone
- email settings if workflows depend on email

## Phase 5: Allow LAN Access

### 1. Use the server PC's LAN IP

On the server PC, get the IPv4 address with:

```powershell
ipconfig
```

Look for the IPv4 address of the active network adapter.

Example:

- `192.168.1.10`

Users will open:

- `http://192.168.1.10:8069`

### 2. Allow Odoo through Windows Firewall

Allow inbound access to:

- TCP `8069` for Odoo

Only allow PostgreSQL remote access if truly needed:

- TCP `5432`

For normal browser access, users only need `8069`.

### 3. Test from another PC

From another PC on the same network:

- open `http://SERVER_IP:8069`
- confirm the login page loads
- log in using a normal user account

## Phase 6: Production-Like Lockdown

Once the first database is created and Logilink is installed, move toward a production-like setup.

### 1. Do not let users manage databases

Your users should not see:

- `Create database`
- `Restore database`
- database manager pages

Operational goal:

- only admins should handle database creation and restore
- users should only receive the final Odoo login URL

### 2. Share only the final login URL

After setup, give users only:

- `http://SERVER_IP:8069`

If Odoo is locked down correctly, that URL should lead them to the intended login page instead of database management.

### 3. Keep master password private

The database master password should be known only by admins/IT.

### 4. Use a fixed production database

Decide which database is the official one, for example:

- `apc_logilink_prod`

Do not create multiple similar databases unless you intentionally want:

- development
- staging
- production

## Phase 7: Validate the Functional Flow

Before calling it ready, test the main Logilink flow:

### 1. Master data

Create sample records for:

- departments
- community members
- suppliers

### 2. Purchase flow

Test:

1. create a `Purchase Request`
2. add request lines
3. approve it
4. confirm a `Purchase Order` is created
5. continue through GRN, Supplier Invoice, and Payment if those flows are part of your process

### 3. Asset flow

Test:

1. create assets
2. test assignment/borrowing
3. confirm statuses and permissions behave correctly

### 4. Multi-user check

Test from at least two different PCs:

- one admin user
- one normal operational user

## Phase 8: Daily Operations

For daily usage on the temporary server PC:

- start PostgreSQL first if it is not already running
- start Odoo from this repo/config
- make sure the PC stays powered on
- do not close the server session while users are working

Treat the PC like a real server:

- no random shutdowns
- no sleep mode
- no frequent network changes

## Phase 9: Backup Plan

Even if this is temporary, take backups seriously.

Minimum practice:

- back up the database regularly
- back up the filestore
- keep a copy of this repo including `custom\apc_logilink`

Do this especially:

- before module upgrades
- before config changes
- before moving to the final server

## Phase 10: Move to the Real Server Later

When ready to move from your PC to a dedicated server:

1. install the same Odoo major version
2. copy the same custom addons
3. move the config carefully
4. restore the latest database backup
5. test Logilink again on the new machine
6. update users to the new server URL/IP

## Recommended Rollout Order

1. Start Odoo on your current PC
2. Create one database yourself
3. Install `Logilink`
4. Create admin and normal users
5. Test from your own machine
6. Test from one other PC on the LAN
7. Validate the main Logilink business flow
8. Lock the setup down so users only log in
9. Run pilot usage with a few real users
10. Move to a dedicated server when stable

## Quick Go-Live Checklist

- Odoo starts without errors
- PostgreSQL is stable
- database created by admin
- `Logilink` installed
- users created
- LAN access works from another PC
- firewall allows `8069`
- users reach login page
- master password kept private
- backup procedure tested

## Notes Specific to Your Project

- Your active custom module is `custom\apc_logilink`
- Your repo also has `custom_addons\access_roles`, which may be useful later for user access management
- Since your Odoo Online database is not being used for the custom module rollout, you can treat this on-prem database as the main working environment

## If Something Goes Wrong

Check these first:

- Odoo service/process is actually running
- PostgreSQL is running
- the server PC IP has not changed
- Windows Firewall is not blocking `8069`
- the user is opening the correct URL
- the module appears in `Apps` after `Update Apps List`

## Suggested Next Step

Use this guide first on your current machine, then once it works, document:

- the final production database name
- the final LAN URL
- the admin owner of the master password
- the backup owner and schedule
