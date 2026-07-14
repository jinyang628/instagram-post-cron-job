.PHONY: lint

lint:
	poetry run black .
	poetry run isort .
	poetry run autoflake --in-place --remove-all-unused-imports --recursive .
