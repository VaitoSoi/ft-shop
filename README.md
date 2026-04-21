# Flavortown Store Webhook API
A simple Webhook API that follows Flavortown store changes.

## Demos:
- Service that follow the real FT store changes: https://ft-shop.vaito.dev/docs#/
- Service that follow the emulated FT store changes: https://ft-test.vaito.dev/docs#/
- FT store emulator: https://ft-api.vaito.dev/docs#/

## I. Introduction
This is a simple webhook API that notify you when an item is:
- added
- updated
- removed

There are two subscription modes:
- **compact** - Only return the path of changed item.

    The response should look like this:
    ```json
    {
        "<item id>.<path>": ["<old_value>", "<new value>"]
    }
    ``` 
    
    Example:
    ```json
    {
        "1.ticket_cost.base_cost": ["15", "10"],
        "2.sale_percentage": ["18", "36"],
        "8.stock": ["67", "69"],
    }
    ```

- **full** - Return the full changed item data

    The response should look like this:
    ```json
    {
        "<item id>": {
            "old": <old_data>,
            "new": <new_data>,
            "changes": ["<path>"]
        }
    }
    ```

    Example:
    ```json
    {
        "1": {
            "old": {
                "id": 1,
                "name": "A dummy item",
                "limited": true,
                "enabled": {
                    "enabled_au": true,
                    "enabled_ca": true,
                    "enabled_eu": true,
                },
                "ticket_cost": {
                    "base_cost": 1,
                    "au": 1,
                    "ca": 1,
                    "eu": 1,
                }
            },
            "new": {
                "id": 1,
                "name": "Just a dummy item",
                "limited": true,
                "enabled": {
                    "enabled_au": true,
                    "enabled_ca": true,
                    "enabled_eu": true,
                },
                "ticket_cost": {
                    "base_cost": 4,
                    "au": 5,
                    "ca": 8,
                    "eu": 1,
                }
            },
            "changes": [
                "name",
                "ticket_cost.base_cost",
                "ticket_cost.au",
                "ticket_cost.ca",
            ]
        }
    }
    ```

When this app notice changes, it will make a POST request to registered endpoint to notify you.

## II. Setup

### 1. Use Docker

Pull the image from the command line:

```bash
docker pull git.vaito.dev/vaito/ft-shop:latest
```

Then run it:

```bash
docker run -e TOKEN=<your flavortown token> -p 8000:8000 -v <path to db.sqlite file>:/app/file/db.sqlite git.vaito.dev/vaito/ft-shop:latest
```

### 2. Pull this repo

Pull this repo:

```bash
git pull https://git.vaito.dev/vaito/ft-shop.git
```

Install the package:

```bash
uv sync --locked
```

Enter the virtual environment:

```bash
source <path/to/virtual/env>
```

And run this app:

```bash
fastapi run app/main.py
```

## III. Env

| Name              | Accept value          | Default value | Note     |
|-------------------|-----------------------|---------------|----------|
| DB_URL            | Any DB connection URL with coressponding async driver | None          | Required <br> Should be accepted by [SQLAlchemy](https://pypi.org/project/SQLAlchemy/) |
| TOKEN             | Flavortown API Token  | None          | Required |
| BASE_URL          | Flavotown API URL     | https://flavortown.hackclub.com/api/v1/ | |
| NOTIFY_WHEN_EMPTY | boolean               | false         | Enable this will let this app send empty `old` fields when startup|
| INTERVAL          | int                   | 10            | Data crawling interval | 
| EXPIRE_TIME       | timedelta             | 7 days        | User token default expire time <br> Should be accepted by [ms library](https://pypi.org/project/python_ms/) |

## IV. Components:

| Package      | Description |
|--------------|-------------|
| fastapi      | Handle API server |
| sqlmodel     | Handle DB part |
| aiohttp      | Handle sending notification |
| pytest       | Handle testing part |
| aioresponses | Handle mocking aiohttp request |
