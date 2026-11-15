FROM public.ecr.aws/lambda/python:3.12

# Install static ffmpeg binary from official yt-dlp/FFmpeg-Builds GitHub releases
RUN dnf install -y tar xz curl && \
    curl -fL https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz | \
    tar -xJ --strip-components=2 -C /usr/local/bin/ --wildcards '*/bin/ffmpeg' '*/bin/ffprobe' && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    dnf clean all

WORKDIR ${LAMBDA_TASK_ROOT}

# Copy project files and static font assets
COPY pyproject.toml ./
COPY fonts/ ./fonts/
COPY config.example.yaml ./config.yaml
COPY src/ ./src/

# Install PodTube and its dependencies
RUN pip install --no-cache-dir .

ENV PODTUBE_SAVE_LOCATION=/tmp/podtube
ENV PODTUBE_FFMPEG_LOCATION=/usr/local/bin/ffmpeg

CMD ["podtube.lambda_handler.handler"]

