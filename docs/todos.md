# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Features

### Export / Import Archives
1) Backup a project folder to an external location, creates a tarball of the entire project folder, including renders.

```bash
# directory only, creates a project-slug.cleave-tar.gz
./cleave.py export project-slug-or-path /path/to/project/backups/

# full filename, creates the file...
./cleave.py export project-slug-or-path /path/to/project/backups/sights-and-sounds-26.tar.gz
```

In both cases it should prompt to overwrite if the backup tarball already exists

2) Restore previous backups back into projects dir...

```bash
# specify full path to project archive...
./cleave.py import /path/to/project/backups/sights-and-sounds-26.tar.gz
# should unpack to the project directory slug specified in the project.yaml 
# if it already exists prompt for delete and replace (default N)

# optionally override the target project dir
./cleave.py import /path/to/project/backups/sights-and-sounds-26.tar.gz --new-project some-new-projects-slug
# this shoudl also rewrite the slug in the project.yaml and leave a record
# imported-from: old-slug
```

## Bug Fixes

### Audio starts before visualizer / render is fully booted
The visualizer app is not fully initialised when auidio starts - confusing UX.
Similar happens when rendering - audio starts before the projectM visualisers.

The correct UX is to wait and show a loading bar / spinner while the app is initialising.
Once everything is ready, the app and audio should start together.

Similarly on render - render no frames until the app is fully initiliased and the projectM instances are confirmed working.

### Disarming track mid-record does unexpected things
Disarming a track before you stop recording, stops the recording but also make the timeline go solid.
When the track is subsequently stopped with space bar... all the recorded elements correctly pop-in on the timeline.