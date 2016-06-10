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

## Installation to a server for public use

Checkout the code:

    git clone git@github.com:priestc/MultiExplorer.git

Then run the install script:

    cd MultiExplorer
    python install.py

Depending on how much load you expect to see you might want to swap out SQLite
with a more sophisticated database such as Postgres. Edit the file in
`MultiExplorer/multiexplorer/multiexplorer/local_settings.py`. Change the value
of `DATABASES` to the following:

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'multiexplorer',
            'USER': 'chris',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '5432',
        }
    }

You might want to change the username to whatever your user account is.

Now navigate to `MultiExplorer/multiexplorer` and run the command:

    python manage.py migrate

Also, you want to use a webserver such as Apache or Nginx. Install by running the following command:

    sudo apt-get install nginx

The move the file `MultiExplorer/multiexplorer.nginx` to `/etc/nginx/sites-enabled/`
and change the paths inside that file to point to the MultiExplorer files where you installed them.

## Updating

To update the code, move to the MultiExplorer folder and run:

    git pull

If you see a message telling you to run `./manage.py migrate`, then navigate to
the `MultiExplorer/multiexplorer/multiexplorer` folder and run that command.
