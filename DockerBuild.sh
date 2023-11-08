docker build -t the-bard .
docker run -it --name the-bard -v $(pwd):/Bard the-bard
