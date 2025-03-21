FROM opensuse/tumbleweed

RUN curl -o- https://dl.stackstate.com/stackstate-cli/install.sh | bash
COPY ./stackpack    /mnt/.
COPY ./deps    /mnt/.
COPY ./init.sh /mnt/.

ENTRYPOINT ["/bin/bash", "/mnt/init.sh"]
