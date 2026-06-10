# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## CI

GitHub Actions workflow on push and pull request:

```bash
./tests/run_unit_tests.py
```

- Linux runner (headless; pygame is initialized in [tests/conftest.py](../tests/conftest.py) without opening a Milkdrop window)
- Install from [requirements.txt](../requirements.txt) (includes `pytest`)
- Optional later: `-m "not slow"` once librosa/audio integration tests are marked `@pytest.mark.slow`
