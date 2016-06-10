# MultiExplorer

## Installation for local personal use

Checkout the code:

    git clone git@github.com:priestc/MultiExplorer.git

Then run the install script

    cd MultiExplorer
    python install.py

Now start the server by running the following command:

    python run_server.py

Point our browser to http://localhost:8000 and you should see MultiExplorer!

## Updating

To update the code, move to the MultiExplorer folder and run:

    git pull

If you see a message telling you to run `./manage.py migrate`, then navigate to
the multiexplorer folder (inside the `MultiExplorer` folder) and run that command.
