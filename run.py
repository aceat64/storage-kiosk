import requests
import dateutil.parser
import os
from time import sleep
from sys import exit
from datetime import datetime, timezone
from dotenv import load_dotenv
from rich import print
from rich.console import Console
from rich.panel import Panel

console = Console()

load_dotenv()

if os.environ.get("COORDINATOR_URL") is None:
    print("COORDINATOR_URL environment variable must be set!")
    exit(1)

coordinator_url = os.environ["COORDINATOR_URL"]
user_agent = "storage-kiosk/0.0.1"


def GET(uri):
    global coordinator_url, user_agent
    return requests.get(f"{coordinator_url}{uri}", headers={"User-Agent": user_agent})


def POST(uri, data):
    global coordinator_url, user_agent
    return requests.post(
        f"{coordinator_url}{uri}", headers={"User-Agent": user_agent}, json=data
    )


def get_page(page):
    with open(f"pages/{page}.txt", "r") as f:
        content = f.read()
        f.close()
    return content


def show_rules():
    console.clear()
    print(Panel(get_page("rules"), title="Rules"))


def promptRFID():
    global coordinator_url, headers

    badge_id = input("Scan RFID Badge: ")

    if not badge_id:
        raise Warning("[yellow]Invalid badge.[/] Please try again.")

    r = POST("/members/", {"badge_id": badge_id})

    if r.status_code == 403:
        raise Warning("[yellow]Badge not found.[/]")
    if r.status_code not in [200, 201]:
        raise Exception(
            "[red]An error occured with the system, please try again later.[/]"
        )

    member = r.json()

    # Validate that they are not currently banned from storage
    if member["banned_until"]:
        banned_until = dateutil.parser.isoparse(
            member["banned_until"],
        )
        if banned_until > datetime.now(timezone.utc):
            raise Exception(
                f"[bold red]You are not allowed to use storage until: {banned_until.astimezone(None)}[/]"
            )

    return member


def checkTickets(member):
    # Check if they have an existing ticket open
    r = GET(f"/tickets/?finished=false&member={member['id']}")
    if r.status_code not in [200, 201]:
        raise Exception(
            "[red]An error occured with the system, please try again later.[/]"
        )
    open_tickets = r.json()

    if open_tickets["count"] != 0:
        # Member has an active ticket
        ticket = open_tickets["results"][0]

        # Close out the member's ticket
        close_ticket = POST(f"/tickets/{ticket['id']}/close/", None)
        if close_ticket.status_code not in [200, 201]:
            raise Exception(
                "[red]An error occured with the system, please try again later.[/]"
            )

        member_lookup = GET(f"/members/{member['id']}/")
        if member_lookup.status_code not in [200, 201]:
            raise Exception(
                "[red]An error occured with the system, please try again later.[/]"
            )

        spot_lookup = GET(f"/spots/{ticket['spot']}/")
        if spot_lookup.status_code not in [200, 201]:
            raise Exception(
                "[red]An error occured with the system, please try again later.[/]"
            )

        return {"member": member_lookup.json(), "spot": spot_lookup.json()}

    return False


def reserveSpot(member):
    spot_name = input("Enter spot name/identifer (e.g. 'a2'): ").strip()

    if not spot_name:
        raise Warning("[yellow]Invalid spot name/identifier.[/] Please try again.")

    r = GET(f"/spots/?search={spot_name}")
    if r.status_code not in [200, 201]:
        raise Exception(
            "[red]An error occured with the system, please try again later.[/]"
        )
    spots = r.json()

    if spots["count"] > 1:
        raise Warning(
            "[yellow]An issue occured when trying to reserve the spot.[/] More than one spot with that name/identifier was found, something is wrong."
        )

    if spots["count"] == 0:
        raise Warning(
            "[yellow]No spot found with that name/identifer, please try again.[/]"
        )

    spot = spots["results"][0]

    # reserve spot
    r = POST(
        "/tickets/",
        {
            "spot": spot["id"],
            "member": member["id"],
        },
    )

    # check that it worked
    if r.status_code == 400:
        ticket = r.json()
        if "spot" in ticket:
            raise Warning(f"[yellow]An error occured: {ticket['spot']}[/]")
        else:
            raise Exception(
                "[red]An error occured with the system, please try again later.[/]"
            )

    if r.status_code not in [200, 201]:
        raise Exception(
            "[red]An error occured with the system, please try again later.[/]"
        )

    ticket = r.json()
    # set ticket["spot_name"] so we can show it to the user
    ticket["spot_name"] = spot_name

    return ticket


if __name__ == "__main__":
    while True:
        show_rules()

        member = None
        attempts = 0
        while attempts < 3:
            try:
                # Wait for an RFID tag
                member = promptRFID()
                existing_ticket = checkTickets(member)
                # No exceptions, so let's break out
                break
            except Warning as msg:
                print(Panel(str(msg)))
            except Exception as msg:
                print(Panel(str(msg)))
                # Exceptions are bad, break out so we hit the 10s pause and reset
                break
            attempts += 1
        if not member:
            # Pause for 10s and then restart the big loop
            sleep(10)
            continue

        if existing_ticket:
            print(
                Panel(
                    f"You have been signed out of your storage spot [green]{existing_ticket['spot']['name']}[/], you may use project storage again after: [green]{existing_ticket['member']['banned_until']}[/]"
                )
            )
            sleep(20)
            continue

        show_rules()
        print(
            Panel(
                f"Hello, [bold]{member['name']}[/].\n\nThe email address we have on file for you is: [bold green]{member['email']}[/]\n\nPlease enter the identifier of the spot you want to use."
            )
        )
        # prompt user to select a spot, and create a ticket
        ticket = None
        attempts = 0
        while attempts < 3:
            try:
                ticket = reserveSpot(member)
                # No exceptions, so let's break out
                break
            except Warning as msg:
                print(Panel(str(msg)))
            except Exception as msg:
                print(Panel(str(msg)))
                # Exceptions are bad, break out so we hit the 10s pause and reset
                break
            attempts += 1
        if not ticket:
            # Pause for 10s and then restart the big loop
            sleep(10)
            continue

        print(
            Panel(
                f"Your spot has been reserved!\n\nYou can use spot [bold]{ticket['spot_name']}[/] until [bold green]{ticket['expires_at']}[/]."
            )
        )
        sleep(20)
