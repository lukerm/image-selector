# Image selector

![](demo.gif)

## Overview

Duplicate photos are annoying and unwanted. Wouldn't you rather make those post-holiday rundowns with the family as impressive (short) as possible? The burden of boiling your photo set
down to the most memorable and ones with the best angle is greatly reduced by this app. It works because you can visualize all images _together_ in the order they were taken.

I now use my Dash app routinely after every holiday, as it makes the deduplication process much faster, yielding a cleaner set of photos without maxing out your hard drive!

First, select the folder that contains the images you want to edit. Confirm that the folder is correct in the dropdown menu, then click "Load images". This may take some time if there
are many images or they are very high resolution.

Select which images belong together by clicking on them. Afterwards, go back through the group choosing the best ones (the s key will save them, indicated by a green border) and the ones
which really must go (the d key will delete them, indicated by a red border). Once you've made a choice for _every_ photo in that group, click "Save group" (or Shft+C) to complete it. 
Click "Shortcuts" to see a list of all available shortcuts.

Repeat until you have filtered down every group in the loaded image directory.

Note: it is important to realise that photos you choose to delete in the app really will be deleted from the folder you are editing. They can, however, be restored from the back up
directory `$HOME/Pictures/_deduplicate_backup/`.

Note: if you click "Save group" / Shft+C when there are no photos selected, it will _save_ the in-focus image as a single-entity group. I found this quite a handy shortcut when working
through my photos.


## Installation: demo mode

The app is built on top of [`Dash`](https://dash.plot.ly/) by plotly. To install all the app's dependencies:

```bash
git clone git@github.com:lukerm/image-selector && cd image-selector
pip install -r requirements.txt
```

In order to get a feel for how the app works, run:

```bash
python selector_app.py --demo
```

Note: Dash provides support for earlier versions of `python`, but I have only tested the app with 3.6 and above.

You should then see output similar to the following. You can use the app by clicking on the local URL on the bottom line.

```bash
 * Serving Flask app "selector_app" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://127.0.0.1:8050/ (Press CTRL+C to quit)
```

When you've arrived in the browser, it's time to explore. Navigate the images with the arrow keys. Get to know all the shortcuts by clicking the "Shortcuts" pop-up. Try to replicate the
example shown in the above GIF in this care-free environment.

Note: This app works only on UNIX-based operating systems (i.e. no support for Windows) even in demo mode. This is, in part, because I assume that `/tmp/` and `~/Pictures/` exist on
your machine (which is not the case for Windows).

## Installation: the real deal

To run the app properly, there are a few more installation steps required - namely, setting up the database to record your activities. I use a PostgreSQL database named `deduplicate`.
You can in principle use whatever name / SQL flavour you prefer so long as you configure it properly in the database section of `config.py`. This should be fairly painless as I've
used the [SQLAlchemy](https://www.sqlalchemy.org/) abstraction toolkit.

Once you've set up the database, execute the `CREATE TABLE` query in `duplicates_table.sql`. Finally, you can run the app like in the demo mode but dropping the `--demo` flag:

```bash
python selector_app.py
```

Test that your database connection is working by:

1. loading a directory of images to edit
2. create a small group of duplicates and label them (save / delete)
3. check that the corresponding number of rows appear in the database table.


## Warning

Please heed the following notes:

* When running this app out of demo mode, the program _will_ delete any photos you choose to discard.
   * They can however be restored by clicking "Undo" in app (or from the `$HOME/Pictures/_deduplicate_backup/` directory in case it unexpectedly crashes).
* The app is only meant to work locally. _Please do not run as an external web server!_
   * The app can and does perform copy / delete operations of files on your machine. It is therefore important not to serve it to untrusted users.
* This program does not have a graceful close if you're halfway through editing an image folder. You cannot restore a previous session.
   * Try to label all the images in your image folder in one sitting.
   * If possible, break a large photo dump into several subfolders before processing them in the app.
   * In case of a power outage or app failure, discarded duplicates will still be removed from your file system (and labels will persist in the database), 
     but it will not be possible to continue editing the folder from where you left off.

If you like this project, please hit the ⭐ button!
