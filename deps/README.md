These files contain lists of dependencies for building, running, and
docker-deploying rse The idea is to have an authoritative
machine-readable list of dependencies, so the documentation cannot get
out of sync with what scripts are actually using.

They're named in a `*.$pkgsystem.txt` pattern for ease of globbing, so please
stick to that format. They are not all-inclusive -- for example, the
'run' list only includes those packages necessary to run rse, not
those necessary for building it. This makes it easy for a script to mix
and match them as needed.

The simplest way to install these on a linux box is like this: `cat
$filename(s) | grep -v ^# | xargs apt-get -y install`

In an ideal universe we'd have a .deb build that took care of installing
these for us, but no such luck for now.
