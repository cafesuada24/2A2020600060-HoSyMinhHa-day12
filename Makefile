.PHONY: run run_docker
run:
	docker compose --env-file .env.local up --build
run_redis:
	docker run --rm -d redis:7-alpine --p 6379:6379
