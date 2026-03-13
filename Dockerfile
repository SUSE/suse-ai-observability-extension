FROM opensuse/tumbleweed AS builder
RUN zypper --non-interactive refresh && \
    zypper --non-interactive install zip
COPY stackpack/suse-ai /build/suse-ai
WORKDIR /build/suse-ai
RUN zip -r /build/suse-ai.sts stackpack.conf provisioning resources

FROM opensuse/tumbleweed
RUN zypper --non-interactive refresh && \
    zypper --non-interactive install jq
RUN curl -o- https://dl.stackstate.com/stackstate-cli/install.sh | bash
COPY --from=builder /build/suse-ai.sts /mnt/suse-ai.sts
COPY init.sh /mnt/init.sh

ENTRYPOINT ["/bin/bash", "/mnt/init.sh"]
