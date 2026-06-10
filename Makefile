.PHONY: test api web docker-up docker-down

test:
	python -m pytest

api:
	uvicorn src.main:app --host 0.0.0.0 --port 8000

web:
	streamlit run ui/app.py --server.address 0.0.0.0 --server.port 8080

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
