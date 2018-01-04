# Battl3ship

The Battl3ship game is like regular Battleship but with 3 twists - you shoot thrice each turn, but only get the
_lengths_ (and not the position) of any hit or sunk ships. 

![Screenshot](https://github.com/miguelinux314/battl3ship/raw/master/doc/shots_screenshot.png "Battl3ship")

The first player sinking all of their opponent's ships wins!

## Rules and Help
* The **goal** of the game is to sink all your opponent's ships.
* First you **place your boats** (4 x length 1, 3 x length 2, 2 x length 3, 4 x length 4) so that:
  * No ship can have another ship in any of its surrounding squares
  * No ship can be entirely placed on the edge
* In each turn, **you shoot on 3 cells. However, you get _imprecise_ results**, combined for all 3 shots:
  * For example, the result "**H1 S4**" means that you **H**it a boat of length **1**, and **S**unk another of length **4**.
  * As another example, "S3" means you sunk a ship of length 3. Note that you will get an identical result if you hit that ship multiple times this turn or only the last remaining square.
  * If you hit the last two remaining squares of a ship (e.g. of length 3) in the same turn, you will receive "S3", but not any "H3" corresponding to that ship in that turn.
* Try to make it **difficult to guess where your ships are placed**:
  * Use horizontal and vertical ships
  * Arrange your ships in seemingly random locations
  
## Installation 
### Dependencies
* Python 2.7: [Windows Installer](https://www.python.org/ftp/python/2.7.14/python-2.7.14.msi), [Mac OSX Installers](https://www.python.org/downloads/release/python-2714/), installed by default in most Linuxes.
* The [Tornado](http://www.tornadoweb.org/en/stable/) python library. You can _either_:
  * Execute `install_dependencies.py`
  * or run `pip install tornado`
  * or go to http://www.tornadoweb.org/en/stable/ and follow their instructions
  
### Run the Game
1. Download the code, decompress and go into `src/`
2. Execute `httpserver.py`
3. Go to [localhost:8080](http://localhost:8080)
4. Other players can join you at http://[Your_public_IP](https://whatismyipaddress.com/):8080
5. Play!

Note that you will have to configure your firewalls to let traffic through port TCP 8080. You may need [instructions for MacOS(not mine)](https://www.macworld.co.uk/how-to/mac-software/how-open-specific-ports-in-os-x-1010-firewall-3616405/) or [instructions for Windows (also not mine)](http://www.tomshardware.com/faq/id-3114787/open-firewall-ports-windows.html).
Don't forget to [forward ports in your router](https://www.pcworld.com/article/244314/how_to_forward_ports_on_your_router.html), too!
