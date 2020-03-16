# Image selector

<> ![](deduplicate_demo.gif)

Duplicate photos are annoying and unwanted. Wouldn't you rather make those post-holiday rundowns with the family as impressive (short) as possible? The burden of boiling your photo set
down to the most memorable, best-angled ones is greatly reduced by this app. This is because you can visualize all images _together_ in the order they were taken.

First, select the folder that contains the images you want to edit. Confirm that the folder is correct in the dropdown menu, then click "Load images". This may take some time if there
are many images or they are very high resolution.

select which images belong together by clicking on them. Afterwards, go back through the group choosing the best ones (the s key will save them, indicated by a green border) and the ones
which really must go (the d key will delete them, indicated by a red border). Once you've made a choice for _every_ photo in that group, click "Save group". Repeat until you have filtered
down every group in the loaded image directory.




App is only meant to work locally, as it can perform copy / delete operations on your machine!
Importantly, running out of demo mode, the program _will_ delete any photos you choose to discard. They can however be restored from the `_deduplicate_backup` directory 
created under `$HOME/Pictures/` (or with 'Undo' if you're still in the app).

Installation: pip install -r requirements.txt

Run: `python selector_app.py --demo`

To run it for real, you'll need to set up postgres database (named "deduplicate") and run the CREATE TABLE query in duplicates_table.sql


Works only on UNIX-based operating systems (i.e. no support for Windows). 


