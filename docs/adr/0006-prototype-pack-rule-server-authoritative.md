# Keep the prototype's Pack rule; the server decides Ticket counts

The brief's "1 kg = 1 ticket, 2 kg = 2, 3 kg = 3" was confirmed by the developer to be an example. We keep the prototype's Packs, prices and lucky-number counts (250 g gives 1, 500 g gives 3, 1 kg gives 8), and each lucky number is one Ticket with an equal chance. The server prices every Order and issues Tickets from its own Pack table, ignoring any price or count the browser sends. This is recorded as an assumption in the README.
