# Multi Agent Demo

> [!TIP]
> Updated for Coral Server v1

## Prerequisites

```bash
./check-dependencies.sh
```

This script will automatically check for valid versions of all prerequisites.

## Running Coral Server

First, make sure you have pulled the coral-server submodule:
```bash
git submodule init
git submodule update
```

Now, we can cd into the coral-server folder, and start it.

```bash
cd coral-server
REGISTRY_FILE_PATH="../registry.toml" ./gradlew run
```

> [!NOTE]
> We use the `REGISTRY_FILE_PATH` environment variable to tell Coral Server where our custom `registry.toml` is.

## Running Coral Studio
```bash
npx @coral-protocol/coral-studio
```
