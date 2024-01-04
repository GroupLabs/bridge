1. Install via brew:

`brew install openjdk@17`

2. Find the appropriate symlink so that the system can find it:

    Run `brew info openjdk@17`

    This will return a line that shows you how to create the symlink.

    E.g.
        For the system Java wrappers to find this JDK, symlink it with:
        sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk
