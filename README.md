# ReCognition Workbench — Device Lifecycle Management

Cloud-based workflow system for device refurbishment, from intake to dispatch.
Built for Birmingham Device Bank (ReCognition CIC).

## Overview

The Workbench manages the complete lifecycle of donated and leased devices:

1. **Intake** — FOG auto-discovery or guarded manual entry
2. **Refurbishment** — Grading, wiping, parts fitting, stage transitions
3. **Stock Management** — Allocation intent, bulk actions, reservation with organisation tracking
4. **Allocation** — Link devices to recipients (businesses, charities, schools, individuals)
5. **Dispatch** — Fulfilment request tracking, ERPNext sync (Phase 6)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.x + Django REST Framework |
| Frontend | Django templates + Tailwind CSS (via CDN) + HTMX |
| Database | PostgreSQL |
| Deployment | Docker Compose + Gunicorn + Caddy |
| Integration | n8n (FOG pipeline, print queue, Cedar ingest) |
| File Storage | SFTP container (Cedar wipe certificates) |

## Key Features

- **Device tracking** — Inventory numbers, specs, grades, wipe status, parts tracking
- **Stage workflow** — Configurable stage transitions with audit trail
- **Stock Available page** — Filter by type/grade/RAM/storage/Win11/intent, bulk update allocation intent, reserve for organisations
- **Allocation system** — Recipient management, reservation, pricing, ERPNext references
- **Manual device entry** — Guarded path for PXE boot failures with audit
- **Windows 11 compatibility** — Auto-calculated from processor spec
- **Barcode scanning** — Quagga2-powered device and location scanning
- **Label printing** — n8n-driven print queue (post-MVP refinement)
- **Cedar integration** — SFTP-based wipe certificate ingestion (in progress)

## Navigation

- **/devices/** — Device list with filters (stage, grade, wipe, parts, intent)
- **/devices/{id}/** — Device detail with stage transition
- **/devices/{id}/edit/** — Edit device fields (grade, intent, specs, wipe, parts)
- **/devices/manual/create/** — Manual device entry (guarded path)
- **/stock/** — Stock Available dashboard with bulk operations
- **/scan/** — Barcode scanner for device/location lookups
- **/admin/** — Django admin for all models

## API Endpoints

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/devices/` | List devices (filterable) |
| `POST` | `/api/devices/` | Create device |
| `GET` | `/api/devices/{id}/` | Device detail |
| `PATCH` | `/api/devices/{id}/` | Update device + spec |
| `POST` | `/api/devices/{id}/update_location/` | Scan device to location |
| `POST` | `/api/devices/{id}/transition/` | Move device to stage |
| `GET` | `/api/stock/overview/` | Summary counts & valuation |
| `GET` | `/api/stock/available/` | Filterable stock list |
| `POST` | `/api/stock/bulk-update/` | Bulk set allocation intent |
| `PATCH` | `/api/devices/{id}/update_intent/` | Single device intent update |

## Data Models

- **Device** — Core tracking: inventory_number, serial_number, device_type, grade, allocation_intent, market_value_pounds, wipe_status, parts_status, win11_compatible
- **DeviceSpecification** — Hardware spec: manufacturer, model, processor, memory, storage (source: FOG/CEDAR/MANUAL)
- **Stage** — Workflow stage with sequence and allowed transitions
- **Location** — Physical shelf location linked to Site
- **Donor** — Device donor organisation/individual
- **Recipient** — Allocation recipient with type, contacts, ERPNext customer ID
- **Allocation** — Device→Recipient link with status (RESERVED/DISPATCHED/CANCELLED), pricing, ERPNext references
- **FulfilmentRequest** — Order from ERPNext: recipient, spec criteria, delivery tracking
- **Manufacturer** — Normalised manufacturer list with slug
- **DonationPledge** — Expected device from donation event, with serial matching

## Quick Start

```bash
git clone <repo-url>
cd workbench-project
cp .env.example .env          # Configure database, API keys, etc.
docker compose up -d          # Starts web, db, caddy, sftp
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
Access at https://your-domain.comDevelopmentdocker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose restart web
InfrastructureServiceContainerPortWeb (Django + Gunicorn)workbench-web—Database (PostgreSQL)workbench-db5432Reverse proxy (Caddy)workbench-caddy443SFTP (Cedar certs)cedar-sftp2222Integration Points
FOG — n8n polls FOG API for new hosts, creates devices with auto-inventoried specs
Cedar — SFTP file watcher ingests wipe certificates (PDF + JSON)
n8n — Orchestrates FOG→Workbench pipeline, label printing, Cedar ingest
ERPNext — Phase 6: Sales Order sync, Customer sync, Delivery Note reconciliation

