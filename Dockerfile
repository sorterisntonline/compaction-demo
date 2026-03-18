FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN python3 -c "import tomllib, subprocess, sys; deps = tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + deps)"

COPY . .

CMD ["python", "-m", "app.app", "/data/beings"]
