import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Lot No","Auction","Initial Price","Name","Phone number","Amount","Submitted At","CPO Amount","CPO Bank","Status"])
ws.append(["L-1","Test Auction A",1000,"Abebe Kebede","251911000001",50000,"Nov. 20, 2025, 1:13 p.m.",5000,"CBE","Winner"])
ws.append(["L-2","Test Auction A",2000,"Abebe Kebede","251911000001",80000,"Nov. 20, 2025, 1:20 p.m.",8000,"CBE","Winner"])
ws.append(["L-3","Test Auction B",500,"Sara Tesfaye","251911000002",30000,"Nov. 21, 2025, 9:00 a.m.",3000,"CBE","Winner"])
wb.save("test_bids.xlsx")