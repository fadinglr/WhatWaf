import sys
import shlex
import time
import subprocess

from lib.cmd import WhatWafParser
from content import (
    detection_main,
    encode
)
from lib.settings import (
    configure_request_headers,
    auto_assign,
    WAF_REQUEST_DETECTION_PAYLOADS,
    BANNER, ISSUES_LINK, HOME
)
from lib.formatter import (
    error,
    info,
    fatal,
    warn,
    success
)


def main():
    opt = WhatWafParser().cmd_parser()

    if not len(sys.argv) > 1:
        error("you failed to provide an option, redirecting to help menu")
        time.sleep(2)
        cmd = "python whatwaf.py --help"
        subprocess.call(shlex.split(cmd))
        exit(0)

    # if you feel that you have to many folders or files in the whatwaf home folder
    # we'll give you an option to clean it free of charge
    if opt.cleanHomeFolder:
        import shutil

        try:
            warn("cleaning home folder, all information will be deleted, if you changed your mind press CNTRL-C now")
            # you have three seconds to change your mind
            time.sleep(3)
            info("attempting to clean home folder")
            shutil.rmtree(HOME)
            info("home folder removed")
        except KeyboardInterrupt:
            fatal("cleaning aborted")
        except OSError:
            fatal("no home folder detected, already cleaned?")
        exit(0)

    if opt.encodePayload:
        spacer = "-" * 30
        payload, load_path = opt.encodePayload
        info("encoding '{}' using '{}'".format(payload, load_path))
        try:
            encoded = encode(payload, load_path)
            success("encoded successfully:")
            print(
                "{}\n{}\n{}".format(
                    spacer, encoded, spacer
                )
            )
        except (AttributeError, ImportError):
            fatal("invalid load path given, check the load path and try again")
        exit(0)

    if opt.encodePayloadList:
        spacer = "-" * 30
        try:
            file_path, load_path = opt.encodePayloadList
            info("encoding payloads from given file '{}' using given tamper '{}'".format(
                file_path, load_path
            ))
            with open(file_path) as payloads:
                encoded = [encode(p.strip(), load_path) for p in payloads.readlines()]
                if opt.saveEncodedPayloads is not None:
                    with open(opt.saveEncodedPayloads, "a+") as save:
                        for item in encoded:
                            save.write(item + "\n")
                    success("saved encoded payloads to file '{}' successfully".format(opt.saveEncodedPayloads))
                else:
                    success("payloads encoded successfully:")
                    print(spacer)
                    for i, item in enumerate(encoded, start=1):
                        print(
                            "#{} {}".format(i, item)
                        )
                    print(spacer)
        except IOError:
            fatal("provided file '{}' appears to not exist, check the path and try again".format(file_path))
        except (AttributeError, ImportError):
            fatal("invalid load path given, check the load path and try again")
        exit(0)

    if opt.updateWhatWaf:
        info("update in progress")
        cmd = shlex.split("git pull origin master")
        subprocess.call(cmd)
        exit(0)

    if not opt.hideBanner:
        print(BANNER)

    format_opts = [opt.sendToYAML, opt.sendToCSV, opt.sendToJSON]
    if opt.formatOutput:
        amount_used = 0
        for item in format_opts:
            if item is True:
                amount_used += 1
        if amount_used > 1:
            warn(
                "multiple file formats have been detected, there is a high probability that this will cause "
                "issues while saving file information. please use only one format at a time"
            )
        elif amount_used == 0:
            warn(
                "output will not be saved to a file as no file format was provided. to save output to file "
                "pass one of the file format flags (IE `-J` for JSON format)", minor=True
            )
    elif any(format_opts) and not opt.formatOutput:
        warn(
            "you've chosen to send the output to a file, but have not formatted the output, no file will be saved "
            "do so by passing the format flag (IE `-F -J` for JSON format)"
        )

    if opt.skipBypassChecks and opt.amountOfTampersToDisplay is not None:
        warn(
            "you've chosen to skip bypass checks and chosen an amount of tamper to display, tampers will be skipped",
            minor=True
        )

    # there is an extra dependency that you need in order
    # for requests to run behind socks proxies, we'll just
    # do a little check to make sure you have it installed
    if opt.runBehindTor or opt.runBehindProxy is not None and "socks" in opt.runBehindProxy:
        try:
            import socks
        except ImportError:
            # if you don't we will go ahead and exit the system with an error message
            error(
                "to run behind socks proxies (like Tor) you need to install pysocks `pip install pysocks`, "
                "otherwise use a different proxy protocol"
            )
            sys.exit(1)

    proxy, agent = configure_request_headers(
        random_agent=opt.useRandomAgent, agent=opt.usePersonalAgent,
        proxy=opt.runBehindProxy, tor=opt.runBehindTor
    )

    if opt.providedPayloads is not None:
        payload_list = [p.strip() if p[0] == " " else p for p in str(opt.providedPayloads).split(",")]
        info("using provided payloads")
    elif opt.payloadList is not None:
        payload_list = [p.strip("\n") for p in open(opt.payloadList).readlines()]
        info("using provided payload file '{}'".format(opt.payloadList))
    else:
        payload_list = WAF_REQUEST_DETECTION_PAYLOADS
        info("using default payloads")

    if opt.saveFingerprints:
        warn(
            "fingerprinting is enabled, all fingerprints (WAF related or not) will be saved for further analysis",
            minor=True
        )

    try:
        if opt.runSingleWebsite:
            url_to_use = auto_assign(opt.runSingleWebsite, ssl=opt.forceSSL)
            info("running single web application '{}'".format(url_to_use))
            detection_main(
                url_to_use, payload_list, agent=agent, proxy=proxy,
                verbose=opt.runInVerbose, skip_bypass_check=opt.skipBypassChecks,
                verification_number=opt.verifyNumber, formatted=opt.formatOutput,
                tamper_int=opt.amountOfTampersToDisplay, use_json=opt.sendToJSON,
                use_yaml=opt.sendToYAML, use_csv=opt.sendToCSV,
                fingerprint_waf=opt.saveFingerprints
            )

        elif opt.runMultipleWebsites:
            info("reading from '{}'".format(opt.runMultipleWebsites))
            with open(opt.runMultipleWebsites) as urls:
                for i, url in enumerate(urls, start=1):
                    url = auto_assign(url.strip(), ssl=opt.forceSSL)
                    info("currently running on site #{} ('{}')".format(i, url))
                    detection_main(
                        url, payload_list, agent=agent, proxy=proxy,
                        verbose=opt.runInVerbose, skip_bypass_check=opt.skipBypassChecks,
                        verification_number=opt.verifyNumber, formatted=opt.formatOutput,
                        tamper_int=opt.amountOfTampersToDisplay, use_json=opt.sendToJSON,
                        use_yaml=opt.sendToYAML, use_csv=opt.sendToCSV,
                        fingerprint_waf=opt.saveFingerprints
                    )
                    print("\n\b")
                    time.sleep(0.5)
    except KeyboardInterrupt:
        fatal("user aborted scanning")
    except Exception as e:
        fatal(
            "WhatWaf has caught an unhandled exception with the error message: '{}'. "
            "You can create an issue here: '{}'".format(
                str(e), ISSUES_LINK
            )
        )
