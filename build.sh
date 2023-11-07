docker build -t the-bard .
docker run -it --name the-bard -v $(pwd):/The-Bard the-bard
