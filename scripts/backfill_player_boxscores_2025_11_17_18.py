"""Backfill player_boxscores for 2025-11-17 and 2025-11-18."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Dict, List

from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb_algo_db import get_pg_engine  # <- same helper used in backfill_games_2025_11_17_18.py
from utils.bref_parser import parse_bref_boxscores
from utils.player_boxscores_loader import replace_player_boxscores


# =======================
# 1) PASTE RAW TABLES HERE
# =======================

RAW_BOXSCORES_2025_11_17 = """

Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
1	Nikola Jokić	DEN		CHI	L	38:38	13	27	.481	1	7	.143	9	12	.750	4	14	18	13	1	2	2	2	36	+10	36.8
2	Jalen Duren	DET		IND	W	28:34	12	13	.923	0	0		7	11	.636	5	10	15	3	0	0	1	3	31	+20	31.5
3	Donovan Mitchell	CLE		MIL	W	35:45	14	22	.636	4	8	.500	5	7	.714	0	5	5	7	1	0	2	4	37	+7	30.2
4	Jamal Murray	DEN		CHI	L	38:16	12	22	.545	5	11	.455	5	5	1.000	0	11	11	4	1	0	2	3	34	-1	27.3
5	Tyrese Maxey	PHI		LAC	W	40:57	13	27	.481	4	11	.364	9	10	.900	0	3	3	6	1	0	4	1	39	+4	26.6
6	Shai Gilgeous-Alexander	OKC	@	NOP	W	28:56	5	9	.556	3	5	.600	10	10	1.000	1	1	2	8	3	1	3	3	23	+32	24.8
7	Mikal Bridges	NYK	@	MIA	L	39:13	9	14	.643	2	4	.500	3	5	.600	1	2	3	4	2	4	2	0	23	-8	22.9
8	Isaiah Hartenstein	OKC	@	NOP	W	26:50	7	10	.700	0	1	.000	2	3	.667	5	2	7	6	4	1	2	1	16	+19	22.0
9	Josh Giddey	CHI	@	DEN	W	30:19	8	12	.667	0	2	.000	5	8	.625	4	10	14	6	0	0	2	3	21	-17	21.4
10	Kel'el Ware	MIA		NYK	W	30:41	7	9	.778	1	1	1.000	1	1	1.000	6	8	14	1	1	3	0	4	16	+8	21.3
11	Pascal Siakam	IND	@	DET	L	33:49	8	17	.471	3	8	.375	10	12	.833	2	5	7	1	1	1	3	2	29	-29	21.0
12	Isaiah Jackson	IND	@	DET	L	26:35	6	7	.857	0	0		4	6	.667	8	2	10	3	2	1	1	5	16	-2	20.7
13	Chet Holmgren	OKC	@	NOP	W	32:49	10	14	.714	3	6	.500	3	4	.750	3	6	9	0	0	1	3	2	26	+23	20.6
14	Ayo Dosunmu	CHI	@	DEN	W	25:50	8	9	.889	1	2	.500	4	5	.800	0	3	3	5	0	0	1	1	21	+25	20.5
15	Kon Knueppel	CHO	@	TOR	L	35:46	9	16	.563	4	10	.400	2	2	1.000	5	2	7	1	3	0	3	4	24	+2	19.6
16	Brandon Ingram	TOR		CHO	W	37:29	9	21	.429	3	6	.500	6	7	.857	2	4	6	3	2	3	5	0	27	+2	19.3
17	Rudy Gobert	MIN		DAL	W	29:06	6	8	.750	0	0		3	6	.500	5	4	9	4	2	1	2	0	15	+19	18.8
18	Quentin Grimes	PHI		LAC	W	35:34	6	10	.600	3	6	.500	4	5	.800	0	2	2	3	1	2	0	2	19	+12	18.3
19	Aaron Gordon	DEN		CHI	L	32:25	10	18	.556	1	5	.200	3	4	.750	5	5	10	0	0	0	0	5	24	+18	18.0
20	Daniss Jenkins	DET		IND	W	33:27	11	21	.524	1	5	.200	3	4	.750	2	0	2	8	1	0	4	4	26	+23	17.7
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
21	Naz Reid	MIN		DAL	W	22:34	9	14	.643	3	6	.500	1	1	1.000	1	11	12	2	0	0	3	2	22	+18	17.4
22	Cameron Johnson	DEN		CHI	L	36:55	6	12	.500	5	7	.714	2	2	1.000	2	2	4	3	0	0	0	0	19	+13	17.1
23	Andre Drummond	PHI		LAC	W	37:56	5	8	.625	1	2	.500	3	4	.750	5	13	18	0	1	0	1	1	14	+2	17.0
24	Sam Merrill	CLE		MIL	W	27:52	7	10	.700	6	9	.667	0	0		1	4	5	0	0	1	1	1	20	+4	17.0
25	Javonte Green	DET		IND	W	27:08	7	11	.636	1	4	.250	5	5	1.000	1	3	4	0	2	0	0	5	20	+4	16.7
26	James Harden	LAC	@	PHI	L	36:47	7	25	.280	2	12	.167	12	12	1.000	1	5	6	5	1	2	4	2	28	+4	16.6
27	Micah Peavy	NOP		OKC	L	24:10	7	9	.778	2	3	.667	0	0		2	2	4	4	0	0	0	2	16	-16	16.5
28	Trey Murphy III	NOP		OKC	L	33:21	6	9	.667	4	5	.800	2	2	1.000	2	3	5	1	3	0	3	3	18	-19	15.9
29	Scottie Barnes	TOR		CHO	W	33:18	8	16	.500	0	1	.000	0	0		3	3	6	6	1	2	1	2	16	-6	15.8
30	Jaden McDaniels	MIN		DAL	W	23:16	4	6	.667	3	4	.750	4	5	.800	0	5	5	3	2	1	3	0	15	+15	15.3
31	Jalen Smith	CHI	@	DEN	W	17:57	6	11	.545	3	6	.500	1	1	1.000	1	7	8	2	2	0	1	2	16	+15	15.1
32	Myles Turner	MIL	@	CLE	L	37:10	4	9	.444	4	5	.800	3	4	.750	1	6	7	2	3	1	2	1	15	+1	15.1
33	Ivica Zubac	LAC	@	PHI	L	33:56	7	13	.538	0	0		0	0		5	8	13	1	1	0	0	1	14	-7	14.9
34	Miles Bridges	CHO	@	TOR	L	38:29	9	22	.409	3	9	.333	1	2	.500	3	5	8	3	3	1	4	1	22	+2	14.8
35	Kevin Huerter	CHI	@	DEN	W	24:00	7	12	.583	4	9	.444	2	2	1.000	0	2	2	1	0	0	1	0	20	-21	14.7
36	LaMelo Ball	CHO	@	TOR	L	27:32	6	19	.316	1	7	.143	7	7	1.000	1	4	5	8	1	0	3	2	20	+6	13.8
37	Luguentz Dort	OKC	@	NOP	W	27:49	5	9	.556	4	6	.667	3	3	1.000	0	1	1	1	1	1	0	4	17	+27	13.8
38	Karl-Anthony Towns	NYK	@	MIA	L	32:37	7	19	.368	1	7	.143	7	7	1.000	4	11	15	2	0	1	4	5	22	+3	13.7
39	Immanuel Quickley	TOR		CHO	W	31:05	6	11	.545	3	8	.375	0	0		0	10	10	4	2	0	3	3	15	+7	13.3
40	Jeremiah Fears	NOP		OKC	L	25:21	9	16	.563	2	5	.400	4	5	.800	0	1	1	1	0	0	3	2	24	-12	13.2
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
41	Davion Mitchell	MIA		NYK	W	32:30	7	12	.583	2	5	.400	2	3	.667	0	3	3	5	0	0	3	1	18	+2	13.0
42	Donte DiVincenzo	MIN		DAL	W	26:19	4	8	.500	3	7	.429	3	4	.750	1	4	5	2	0	2	1	1	14	+35	12.9
43	Dru Smith	MIA		NYK	W	15:30	3	5	.600	3	4	.750	2	2	1.000	1	2	3	3	1	0	0	1	11	0	12.7
44	Moussa Diabaté	CHO	@	TOR	L	19:35	3	3	1.000	0	0		2	3	.667	2	5	7	2	0	4	1	1	8	+9	12.4
45	Ryan Rollins	MIL	@	CLE	L	28:46	9	22	.409	5	10	.500	1	1	1.000	0	3	3	5	1	0	4	3	24	+1	12.4
46	Simone Fontecchio	MIA		NYK	W	20:36	5	11	.455	4	7	.571	0	0		0	4	4	3	2	0	0	4	14	+5	12.0
47	Josh Hart	NYK	@	MIA	L	34:05	6	11	.545	0	3	.000	2	3	.667	1	4	5	9	2	1	6	3	14	-11	12.0
48	Miles McBride	NYK	@	MIA	L	38:44	10	23	.435	5	12	.417	0	1	.000	0	4	4	0	0	0	1	2	25	+3	11.9
49	Jakob Poeltl	TOR		CHO	W	31:41	6	7	.857	0	0		1	2	.500	1	8	9	1	0	0	1	3	13	+6	11.7
50	Bennedict Mathurin	IND	@	DET	L	25:15	7	16	.438	3	9	.333	8	14	.571	0	3	3	2	1	0	4	5	25	-16	11.5
51	Collin Sexton	CHO	@	TOR	L	27:45	5	12	.417	2	6	.333	5	6	.833	1	2	3	2	0	0	1	1	17	-4	11.5
52	Jarrett Allen	CLE		MIL	W	24:46	4	7	.571	0	0		4	4	1.000	2	4	6	2	0	1	2	0	12	0	11.4
53	Isaiah Joe	OKC	@	NOP	W	26:12	5	11	.455	4	10	.400	0	0		1	2	3	4	0	0	1	0	14	-1	11.4
54	VJ Edgecombe	PHI		LAC	W	37:19	6	13	.462	2	6	.333	0	2	.000	1	5	6	6	0	0	0	5	14	+4	10.9
55	Dean Wade	CLE		MIL	W	27:32	2	3	.667	1	2	.500	0	0		0	8	8	3	2	1	0	0	5	+14	10.9
56	Kobe Sanders	LAC	@	PHI	L	30:24	5	11	.455	3	7	.429	4	4	1.000	0	1	1	1	1	0	1	4	17	0	10.7
57	Pelle Larsson	MIA		NYK	W	26:16	4	9	.444	2	4	.500	3	4	.750	0	7	7	4	0	0	2	1	13	-4	10.4
58	Giannis Antetokounmpo	MIL	@	CLE	L	13:00	6	10	.600	0	0		2	3	.667	2	3	5	4	1	0	4	2	14	0	10.3
59	Cooper Flagg	DAL	@	MIN	L	26:51	6	10	.600	2	3	.667	1	2	.500	0	1	1	2	0	0	1	1	15	-27	10.3
60	Karlo Matković	NOP		OKC	L	21:50	4	5	.800	2	3	.667	0	0		1	5	6	2	0	1	1	3	10	+4	10.2
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
61	A.J. Green	MIL	@	CLE	L	40:29	4	10	.400	4	8	.500	0	0		0	3	3	4	1	0	0	3	12	-10	10.1
62	Craig Porter Jr.	CLE		MIL	W	20:08	5	6	.833	1	2	.500	0	0		0	1	1	0	2	0	1	0	11	+8	10.1
63	Brandon Williams	DAL	@	MIN	L	24:17	4	12	.333	1	3	.333	6	6	1.000	1	4	5	2	1	1	2	3	15	-8	10.0
64	Jordan Hawkins	NOP		OKC	L	25:24	5	11	.455	1	5	.200	0	0		0	2	2	6	0	0	0	1	11	+5	9.7
65	Bobby Portis	MIL	@	CLE	L	26:43	3	7	.429	1	3	.333	4	6	.667	1	5	6	0	1	0	0	0	11	-13	9.7
66	Duncan Robinson	DET		IND	W	34:17	4	12	.333	3	11	.273	2	3	.667	1	1	2	4	2	0	1	3	13	+8	9.4
67	Norman Powell	MIA		NYK	W	31:43	9	20	.450	0	3	.000	1	1	1.000	0	1	1	3	1	0	2	2	19	+4	9.2
68	Jordan Clarkson	NYK	@	MIA	L	26:03	7	13	.538	0	3	.000	0	0		0	3	3	3	1	0	1	4	14	-17	9.1
69	Gradey Dick	TOR		CHO	W	19:21	3	5	.600	2	3	.667	2	2	1.000	1	0	1	2	0	0	0	2	10	+6	9.0
70	Bogdan Bogdanović	LAC	@	PHI	L	26:29	3	9	.333	1	6	.167	2	3	.667	0	7	7	5	1	0	0	3	9	+3	8.9
71	Jaden Hardy	DAL	@	MIN	L	13:43	4	9	.444	4	5	.800	5	6	.833	1	2	3	0	0	0	4	1	17	+5	8.8
72	Branden Carlson	OKC	@	NOP	W	10:37	2	5	.400	1	3	.333	2	4	.500	3	1	4	2	0	2	0	0	7	-3	8.7
73	RJ Barrett	TOR		CHO	W	32:54	7	16	.438	1	4	.250	1	3	.333	0	3	3	3	1	0	1	3	16	+1	8.6
74	Nicolas Batum	LAC	@	PHI	L	20:47	3	7	.429	3	7	.429	2	2	1.000	0	6	6	1	1	0	1	3	11	0	8.6
75	Mitchell Robinson	NYK	@	MIA	L	18:29	2	3	.667	0	0		1	2	.500	5	6	11	1	1	0	1	2	5	+4	8.5
76	Jevon Carter	CHI	@	DEN	W	18:08	5	13	.385	5	10	.500	0	0		1	3	4	1	0	0	1	2	15	+20	8.4
77	Matas Buzelis	CHI	@	DEN	W	29:05	5	14	.357	2	5	.400	1	1	1.000	2	2	4	2	0	2	1	2	13	-14	8.2
78	Anthony Edwards	MIN		DAL	W	29:24	5	14	.357	1	7	.143	2	2	1.000	1	3	4	3	2	0	2	2	13	+14	8.1
79	Caris LeVert	DET		IND	W	17:26	4	8	.500	0	3	.000	0	1	.000	1	4	5	8	0	0	3	0	8	-1	8.1
80	Andrew Nembhard	IND	@	DET	L	31:31	4	10	.400	1	3	.333	6	6	1.000	1	0	1	4	0	1	5	2	15	-14	8.0
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
81	P.J. Washington	DAL	@	MIN	L	24:53	5	12	.417	1	3	.333	2	2	1.000	0	7	7	2	1	0	2	3	13	-7	7.9
82	Trendon Watford	PHI		LAC	W	18:56	4	6	.667	0	0		0	0		1	3	4	4	1	0	1	5	8	+10	7.8
83	Ryan Kalkbrenner	CHO	@	TOR	L	28:28	2	3	.667	0	0		3	4	.750	1	9	10	0	0	2	2	1	7	-14	7.7
84	Paul Reed	DET		IND	W	13:28	2	3	.667	0	1	.000	3	4	.750	1	1	2	3	1	1	1	4	7	-3	7.5
85	Kris Dunn	LAC	@	PHI	L	27:06	3	5	.600	1	2	.500	0	0		1	1	2	5	1	0	1	5	7	-8	7.2
86	Evan Mobley	CLE		MIL	W	36:02	4	9	.444	1	2	.500	5	8	.625	0	6	6	6	0	1	6	4	14	+5	7.2
87	Paul George	PHI		LAC	W	21:06	2	9	.222	1	4	.250	4	7	.571	0	7	7	3	0	2	1	0	9	-9	6.9
88	John Collins	LAC	@	PHI	L	27:15	3	8	.375	0	0		5	5	1.000	1	6	7	0	0	0	1	4	11	-2	6.5
89	Isaiah Stewart	DET		IND	W	20:26	3	7	.429	2	5	.400	2	2	1.000	1	1	2	0	0	5	2	6	10	+10	6.4
90	Kyle Kuzma	MIL	@	CLE	L	24:09	4	12	.333	1	3	.333	1	1	1.000	2	3	5	2	1	0	0	4	10	+2	6.3
91	Landry Shamet	NYK	@	MIA	L	39:26	2	11	.182	1	7	.143	5	6	.833	0	3	3	4	0	1	0	2	10	+14	6.3
92	Peyton Watson	DEN		CHI	L	34:02	2	4	.500	1	1	1.000	0	0		0	3	3	1	1	3	1	1	5	+5	6.3
93	Gary Trent Jr.	MIL	@	CLE	L	31:27	5	10	.500	2	5	.400	0	0		0	2	2	0	1	0	2	1	12	-18	6.2
94	Mike Conley	MIN		DAL	W	15:41	2	4	.500	1	3	.333	0	0		0	2	2	3	3	0	1	4	5	+17	6.1
95	Ron Holland	DET		IND	W	30:31	3	6	.500	1	2	.500	0	0		1	6	7	2	1	2	3	3	7	+6	6.1
96	Nikola Vučević	CHI	@	DEN	W	29:00	3	13	.231	2	8	.250	0	0		1	8	9	6	1	0	1	4	8	-12	5.8
97	Jarace Walker	IND	@	DET	L	28:27	2	4	.500	1	2	.500	3	5	.600	2	1	3	1	2	0	3	2	8	-9	5.8
98	Ben Sheppard	IND	@	DET	L	28:41	2	7	.286	0	4	.000	0	0		1	3	4	4	1	1	0	1	4	-3	5.6
99	Joan Beringer	MIN		DAL	W	7:46	2	4	.500	0	0		2	2	1.000	1	3	4	0	0	1	0	2	6	-5	5.5
100	Jaylen Clark	MIN		DAL	W	18:47	2	5	.400	1	4	.250	0	0		4	2	6	0	1	0	0	3	5	+15	5.5
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
101	Patrick Williams	CHI	@	DEN	W	16:58	2	7	.286	1	4	.250	2	2	1.000	1	1	2	2	1	0	0	2	7	+4	5.5
102	Julius Randle	MIN		DAL	W	26:54	4	16	.250	1	5	.200	3	5	.600	1	5	6	4	1	0	1	3	12	+21	5.4
103	Lonzo Ball	CLE		MIL	W	23:04	2	8	.250	1	6	.167	1	2	.500	0	5	5	5	2	0	1	4	6	+11	5.2
104	Tre Mann	CHO	@	TOR	L	12:19	2	3	.667	0	1	.000	0	0		0	1	1	0	3	0	0	2	4	-3	5.2
105	Derik Queen	NOP		OKC	L	26:26	3	10	.300	0	0		3	4	.750	5	3	8	3	2	2	6	4	9	-7	5.1
106	Caleb Martin	DAL	@	MIN	L	17:33	2	4	.500	0	1	.000	2	2	1.000	0	3	3	1	1	1	2	1	6	-10	4.9
107	Dalen Terry	CHI	@	DEN	W	18:04	2	4	.500	1	3	.333	0	0		0	3	3	4	0	0	1	2	5	+18	4.9
108	Dominick Barlow	PHI		LAC	W	21:12	3	4	.750	0	0		1	2	.500	0	1	1	0	3	0	2	4	7	-13	4.7
109	Yves Missi	NOP		OKC	L	21:54	3	6	.500	0	0		0	0		1	1	2	2	1	1	2	1	6	-15	4.7
110	Jaime Jaquez Jr.	MIA		NYK	W	32:28	5	11	.455	1	2	.500	2	2	1.000	0	1	1	4	0	0	5	2	13	0	4.6
111	De'Andre Hunter	CLE		MIL	W	25:35	5	11	.455	1	4	.250	0	0		0	5	5	1	0	0	2	3	11	-3	4.3
112	Sandro Mamukelashvili	TOR		CHO	W	14:51	3	7	.429	1	2	.500	0	0		1	3	4	1	0	1	1	3	7	-3	4.1
113	Chaz Lanier	DET		IND	W	18:24	1	3	.333	1	3	.333	0	0		1	1	2	1	1	0	0	0	3	+2	4.0
114	Pat Connaughton	CHO	@	TOR	L	9:03	1	2	.500	0	1	.000	3	4	.750	0	1	1	0	0	0	0	0	5	-4	3.9
115	Ajay Mitchell	OKC	@	NOP	W	25:51	4	14	.286	0	4	.000	3	4	.750	0	2	2	1	1	0	0	2	11	-18	3.9
116	Julian Phillips	CHI	@	DEN	W	10:42	1	4	.250	0	2	.000	0	0		2	1	3	1	1	1	0	0	2	+8	3.7
117	Jamal Shead	TOR		CHO	W	20:11	1	2	.500	0	1	.000	0	0		0	2	2	4	2	1	3	1	2	-7	3.7
118	Moussa Cisse	DAL	@	MIN	L	25:30	2	6	.333	0	0		1	7	.143	4	6	10	0	1	2	1	4	5	-20	3.6
119	Jay Huff	IND	@	DET	L	8:03	2	4	.500	1	3	.333	0	0		0	0	0	0	0	1	0	1	5	-4	3.3
120	Bones Hyland	MIN		DAL	W	7:46	1	2	.500	0	1	.000	0	0		0	2	2	1	1	0	0	0	2	-5	3.3
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
121	Cason Wallace	OKC	@	NOP	W	28:17	3	10	.300	1	4	.250	0	0		0	2	2	4	3	0	3	4	7	+14	3.0
122	Klay Thompson	DAL	@	MIN	L	17:11	3	9	.333	1	6	.167	0	0		0	0	0	0	2	0	1	0	7	-17	2.9
123	Tim Hardaway Jr.	DEN		CHI	L	16:12	2	8	.250	0	3	.000	0	0		1	1	2	0	3	0	0	1	4	-21	2.8
124	Jeremiah Robinson-Earl	IND	@	DET	L	20:22	2	8	.250	0	2	.000	0	0		3	6	9	0	0	0	0	1	4	+14	2.7
125	Jericho Sims	MIL	@	CLE	L	11:31	1	2	.500	0	0		0	0		1	1	2	1	0	0	0	0	2	-8	2.7
126	Brooks Barnhizer	OKC	@	NOP	W	7:10	1	1	1.000	0	0		0	0		0	2	2	1	0	0	0	1	2	-5	2.6
127	Chris Youngblood	OKC	@	NOP	W	2:43	1	1	1.000	1	1	1.000	0	0		0	1	1	0	0	0	0	1	3	-1	2.6
128	Isaac Okoro	CHI	@	DEN	W	19:57	1	3	.333	0	2	.000	0	0		1	0	1	1	0	1	0	0	2	-11	2.4
129	Cole Anthony	MIL	@	CLE	L	21:30	2	8	.250	0	0		0	0		0	1	1	8	0	0	2	2	4	-11	2.3
130	Miles Kelly	DAL	@	MIN	L	9:05	1	2	.500	0	1	.000	0	0		1	3	4	0	0	0	0	1	2	+3	2.2
131	Jose Alvarado	NOP		OKC	L	22:47	3	9	.333	0	4	.000	0	0		1	1	2	1	2	0	1	4	6	-5	2.0
132	Bryce McGowens	NOP		OKC	L	12:32	1	3	.333	0	0		2	2	1.000	0	3	3	0	0	0	0	3	4	+12	2.0
133	Jalen Pickett	DEN		CHI	L	10:27	1	3	.333	1	1	1.000	0	0		1	0	1	0	0	0	0	0	3	+9	2.0
134	Nae'Qwan Tomlin	CLE		MIL	W	12:11	1	2	.500	0	1	.000	0	0		1	1	2	1	0	1	1	1	2	+9	2.0
135	Brook Lopez	LAC	@	PHI	L	14:02	2	5	.400	1	3	.333	1	1	1.000	0	1	1	0	0	0	1	2	6	+5	1.8
136	Chris Paul	LAC	@	PHI	L	11:13	1	2	.500	1	1	1.000	0	0		0	2	2	0	0	0	0	2	3	-6	1.8
137	Joe Ingles	MIN		DAL	W	6:50	0	0		0	0		0	0		0	0	0	1	1	0	0	0	0	-7	1.7
138	Johnny Juzang	MIN		DAL	W	2:59	1	2	.500	1	2	.500	0	0		0	0	0	0	0	0	0	1	3	+5	1.6
139	Collin Murray-Boyles	TOR		CHO	W	15:22	1	3	.333	0	0		2	2	1.000	0	1	1	1	0	0	1	2	4	+2	1.5
140	Nikola Jović	MIA		NYK	W	14:59	2	7	.286	1	4	.250	0	0		0	1	1	2	0	0	0	3	5	-3	1.4
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
141	Mohamed Diawara	NYK	@	MIA	L	1:23	0	0		0	0		0	0		0	1	1	0	1	0	0	0	0	+1	1.3
142	Rob Dillingham	MIN		DAL	W	12:58	4	12	.333	0	3	.000	0	0		0	1	1	1	2	0	2	3	8	-17	1.0
143	Isaac Jones	DET		IND	W	1:19	1	2	.500	0	1	.000	0	0		0	0	0	0	0	0	0	0	2	-3	1.0
144	Naji Marshall	DAL	@	MIN	L	23:15	3	9	.333	0	3	.000	1	3	.333	0	3	3	0	1	0	2	0	7	-24	1.0
145	Guerschon Yabusele	NYK	@	MIA	L	10:00	0	0		0	0		0	0		0	3	3	0	0	0	0	0	0	+1	0.9
146	Cam Christie	LAC	@	PHI	L	12:01	1	2	.500	0	1	.000	0	0		0	0	0	0	0	1	1	0	2	+1	0.7
147	Ousmane Dieng	OKC	@	NOP	W	4:19	0	1	.000	0	1	.000	0	0		0	0	0	2	0	0	0	0	0	-1	0.7
148	Monte Morris	IND	@	DET	L	2:11	1	1	1.000	0	0		0	0		0	0	0	0	0	0	1	0	2	+3	0.7
149	Taelon Peter	IND	@	DET	L	2:11	0	0		0	0		0	0		0	0	0	1	0	0	0	0	0	+3	0.7
150	Drew Peterson	CHO	@	TOR	L	16:08	0	3	.000	0	2	.000	1	2	.500	1	0	1	1	0	1	0	0	1	0	0.6
151	Dwight Powell	DAL	@	MIN	L	16:33	0	0		0	0		0	1	.000	2	3	5	1	0	0	0	5	0	+11	0.6
152	D'Angelo Russell	DAL	@	MIN	L	22:24	4	11	.364	0	5	.000	0	0		1	1	2	4	0	0	4	3	8	-11	0.5
153	Leonard Miller	MIN		DAL	W	9:40	0	2	.000	0	2	.000	0	0		0	3	3	3	1	0	1	3	0	-5	0.4
154	Andrew Wiggins	MIA		NYK	W	32:57	3	15	.200	0	4	.000	0	0		0	4	4	4	0	1	0	3	6	+1	0.2
155	Justin Edwards	PHI		LAC	W	18:02	0	6	.000	0	4	.000	0	0		2	3	5	4	0	0	0	2	0	+1	0.1
156	Jared McCain	PHI		LAC	W	5:06	0	0		0	0		0	0		0	0	0	0	0	0	0	0	0	-2	0.0
157	Thomas Bryant	CLE		MIL	W	7:05	0	1	.000	0	1	.000	0	0		0	2	2	0	0	0	0	0	0	+5	-0.1
158	Gary Harris	MIL	@	CLE	L	5:15	1	3	.333	0	2	.000	0	0		0	0	0	0	0	0	0	1	2	-4	-0.1
159	Keshad Johnson	MIA		NYK	W	2:20	0	2	.000	0	1	.000	0	0		0	2	2	0	0	1	0	0	0	-3	-0.1
160	Max Christie	DAL	@	MIN	L	18:45	0	1	.000	0	0		1	2	.500	0	0	0	1	0	0	1	0	1	-15	-0.4
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
161	Jonas Valančiūnas	DEN		CHI	L	4:33	0	1	.000	0	0		2	2	1.000	0	2	2	0	0	0	2	1	2	-15	-0.5
162	Jabari Walker	PHI		LAC	W	3:52	0	1	.000	0	0		0	0		0	0	0	0	0	0	0	0	0	+1	-0.7
163	Wendell Moore Jr.	DET		IND	W	15:00	0	2	.000	0	0		0	0		0	2	2	0	1	0	1	0	0	+9	-0.8
164	Sion James	CHO	@	TOR	L	24:55	0	4	.000	0	4	.000	0	0		0	5	5	2	1	1	2	2	0	-4	-1.0
165	Spencer Jones	DEN		CHI	L	6:01	0	0		0	0		0	0		0	0	0	0	0	0	1	0	0	-16	-1.0
166	Bruce Brown	DEN		CHI	L	22:32	0	2	.000	0	1	.000	0	0		0	2	2	0	0	0	0	1	0	-17	-1.2
167	Tony Bradley	IND	@	DET	L	17:29	1	6	.167	0	0		2	2	1.000	3	2	5	1	0	0	3	5	4	-10	-1.4
168	Ja'Kobe Walter	TOR		CHO	W	3:48	0	0		0	0		0	0		0	1	1	0	0	0	1	2	0	+2	-1.5
169	T.J. McConnell	IND	@	DET	L	15:26	0	4	.000	0	0		0	0		0	1	1	2	1	0	1	2	0	-8	-1.9
170	Herbert Jones	NOP		OKC	L	26:15	1	8	.125	1	3	.333	2	2	1.000	0	2	2	1	1	0	4	3	5	-32	-3.1
171	Jaylin Williams	OKC	@	NOP	W	18:27	0	2	.000	0	1	.000	0	0		0	5	5	1	0	0	4	2	0	-1	-4.0
"""
RAW_BOXSCORES_2025_11_18 = """

Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
1	Jimmy Butler	GSW	@	ORL	L	38:14	10	16	.625	0	1	.000	13	15	.867	1	6	7	4	3	0	3	0	33	-1	30.3
2	Luka Dončić	LAL		UTA	W	34:14	11	22	.500	2	10	.200	13	16	.813	0	5	5	10	4	0	8	4	37	+10	27.7
3	Stephen Curry	GSW	@	ORL	L	34:13	12	23	.522	7	15	.467	3	5	.600	0	3	3	9	3	0	5	2	34	-3	26.3
4	Keyonte George	UTA	@	LAL	L	35:21	13	23	.565	5	13	.385	3	3	1.000	0	4	4	8	2	0	4	4	34	-9	26.3
5	Lauri Markkanen	UTA	@	LAL	L	32:01	12	21	.571	3	9	.333	4	4	1.000	2	3	5	2	2	0	1	4	31	-6	24.2
6	Jalen Johnson	ATL		DET	L	39:06	8	18	.444	3	8	.375	6	6	1.000	0	8	8	9	3	1	4	2	25	-7	23.2
7	Jalen Duren	DET	@	ATL	W	28:54	8	12	.667	0	0		8	11	.727	4	4	8	3	2	1	2	4	24	+4	22.8
8	Michael Porter Jr.	BRK		BOS	L	33:42	8	16	.500	4	8	.500	5	5	1.000	2	4	6	2	3	0	1	1	25	-9	22.6
9	Harrison Barnes	SAS		MEM	W	32:09	9	14	.643	4	8	.500	1	1	1.000	0	5	5	3	1	0	0	1	23	+3	21.0
10	Desmond Bane	ORL		GSW	W	39:10	7	16	.438	2	6	.333	7	7	1.000	1	5	6	5	5	0	3	4	23	-5	20.7
11	Deandre Ayton	LAL		UTA	W	30:00	10	13	.769	0	0		0	2	.000	4	10	14	1	1	1	1	2	20	+10	20.5
12	Wendell Carter Jr.	ORL		GSW	W	35:07	5	7	.714	1	3	.333	6	6	1.000	4	8	12	2	1	0	1	3	17	-1	19.5
13	Devin Booker	PHO	@	POR	W	29:03	6	13	.462	1	2	.500	6	6	1.000	1	5	6	5	3	0	1	2	19	+17	19.2
14	Cade Cunningham	DET	@	ATL	W	33:49	10	23	.435	1	7	.143	4	4	1.000	0	6	6	10	2	0	3	4	25	+3	19.1
15	Austin Reaves	LAL		UTA	W	33:26	7	11	.636	1	4	.250	11	12	.917	1	4	5	1	1	0	4	3	26	+10	19.1
16	Shaedon Sharpe	POR		PHO	L	29:40	12	24	.500	0	6	.000	5	7	.714	0	2	2	3	1	0	2	0	29	-20	17.9
17	De'Aaron Fox	SAS		MEM	W	33:12	10	20	.500	3	8	.375	3	4	.750	0	1	1	3	2	1	2	3	26	+7	17.5
18	Payton Pritchard	BOS	@	BRK	W	35:15	6	16	.375	5	12	.417	5	5	1.000	2	8	10	5	0	0	3	1	22	+11	17.1
19	Dyson Daniels	ATL		DET	L	37:35	6	9	.667	0	0		0	0		4	5	9	6	3	1	3	1	12	+4	16.9
20	Day'Ron Sharpe	BRK		BOS	L	17:54	7	10	.700	0	2	.000	2	3	.667	3	4	7	2	3	0	1	3	16	-4	16.9
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
21	Anthony Black	ORL		GSW	W	32:45	8	13	.615	0	3	.000	5	7	.714	0	4	4	2	2	0	1	3	21	+18	16.7
22	LeBron James	LAL		UTA	W	29:37	4	7	.571	2	3	.667	1	4	.250	1	2	3	12	1	0	1	0	11	+1	16.2
23	Collin Gillespie	PHO	@	POR	W	28:11	6	11	.545	4	9	.444	3	3	1.000	0	3	3	6	1	0	3	3	19	+1	15.6
24	Daniss Jenkins	DET	@	ATL	W	29:40	6	10	.600	1	4	.250	1	2	.500	0	3	3	7	2	0	1	1	14	+8	15.4
25	Jaylen Brown	BOS	@	BRK	W	32:00	9	19	.474	3	7	.429	8	10	.800	1	3	4	4	1	0	8	2	29	+2	15.1
26	Vince Williams Jr.	MEM	@	SAS	L	29:50	5	13	.385	1	5	.200	3	4	.750	4	5	9	9	0	0	1	3	14	+11	14.9
27	Mark Williams	PHO	@	POR	W	21:16	7	9	.778	0	0		1	2	.500	4	2	6	1	2	1	2	3	15	+15	14.7
28	Nickeil Alexander-Walker	ATL		DET	L	36:43	9	20	.450	1	9	.111	5	6	.833	0	3	3	3	0	0	0	4	24	-19	14.6
29	Jake LaRavia	LAL		UTA	W	25:30	6	10	.600	2	5	.400	2	3	.667	0	4	4	2	1	0	0	1	16	+12	14.2
30	Keldon Johnson	SAS		MEM	W	30:14	8	15	.533	1	5	.200	1	1	1.000	0	7	7	2	2	0	2	1	18	+11	13.8
31	Donovan Clingan	POR		PHO	L	23:27	3	8	.375	0	0		3	3	1.000	7	5	12	2	0	5	2	1	9	-15	13.5
32	Deni Avdija	POR		PHO	L	29:11	7	17	.412	2	6	.333	3	4	.750	1	4	5	5	0	0	1	2	19	-23	13.1
33	Cedric Coward	MEM	@	SAS	L	25:30	7	15	.467	5	7	.714	0	0		2	9	11	1	0	0	3	0	19	+3	13.1
34	Franz Wagner	ORL		GSW	W	36:23	7	17	.412	0	3	.000	4	4	1.000	1	7	8	3	1	1	1	4	18	+5	12.9
35	Oso Ighodaro	PHO	@	POR	W	16:05	6	7	.857	0	0		2	2	1.000	3	1	4	1	0	0	1	2	14	+7	12.8
36	Onyeka Okongwu	ATL		DET	L	33:35	8	13	.615	4	7	.571	1	1	1.000	0	1	1	3	1	2	5	6	21	-22	12.5
37	Isaiah Stewart	DET	@	ATL	W	26:10	4	7	.571	0	0		5	5	1.000	2	7	9	3	0	0	2	2	13	+6	12.5
38	Caleb Love	POR		PHO	L	32:07	7	14	.500	3	8	.375	0	0		1	6	7	3	1	0	3	1	17	+8	12.2
39	Jalen Suggs	ORL		GSW	W	31:56	4	11	.364	0	7	.000	5	5	1.000	0	5	5	8	2	1	3	4	13	+8	12.1
40	Cam Spencer	MEM	@	SAS	L	23:39	6	10	.600	3	7	.429	0	0		0	2	2	3	0	0	1	1	15	-23	11.7
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
41	Mouhamed Gueye	ATL		DET	L	21:24	5	10	.500	1	5	.200	0	0		7	4	11	1	0	1	1	3	11	+17	11.3
42	Draymond Green	GSW	@	ORL	L	31:24	5	8	.625	2	5	.400	0	0		0	6	6	6	0	2	3	4	12	+9	11.2
43	Ryan Dunn	PHO	@	POR	W	26:32	4	8	.500	1	1	1.000	0	0		0	3	3	4	5	0	1	4	9	+23	11.1
44	Duncan Robinson	DET	@	ATL	W	30:41	5	10	.500	4	9	.444	0	0		1	2	3	3	1	0	2	1	14	+4	11.0
45	Sam Hauser	BOS	@	BRK	W	22:01	3	7	.429	2	5	.400	0	0		1	6	7	3	2	0	0	0	8	+22	10.9
46	Tristan Da Silva	ORL		GSW	W	28:52	6	13	.462	3	7	.429	0	0		2	2	4	2	1	0	2	0	15	+6	10.7
47	Jusuf Nurkić	UTA	@	LAL	L	28:52	4	5	.800	0	1	.000	2	2	1.000	2	8	10	6	2	0	6	4	10	-13	10.5
48	Svi Mykhailiuk	UTA	@	LAL	L	25:12	5	7	.714	3	5	.600	0	0		0	3	3	1	0	0	1	2	13	-5	9.9
49	Josh Minott	BOS	@	BRK	W	19:15	3	4	.750	3	3	1.000	1	2	.500	2	2	4	0	0	0	0	1	10	+15	9.6
50	Kelly Olynyk	SAS		MEM	W	18:34	3	6	.500	1	4	.250	3	4	.750	0	5	5	3	2	0	1	4	10	+15	9.6
51	Anfernee Simons	BOS	@	BRK	W	26:09	3	4	.750	2	3	.667	3	5	.600	0	4	4	5	0	0	3	2	11	0	9.5
52	Derrick White	BOS	@	BRK	W	32:47	6	15	.400	3	10	.300	0	0		0	5	5	4	2	2	4	3	15	+15	9.4
53	Santi Aldama	MEM	@	SAS	L	25:52	4	10	.400	0	2	.000	2	2	1.000	2	4	6	2	1	1	1	0	10	-2	9.3
54	Jordan Goodwin	PHO	@	POR	W	21:48	4	10	.400	2	5	.400	0	0		2	2	4	1	3	1	1	2	10	+1	9.2
55	Tyus Jones	ORL		GSW	W	14:55	3	3	1.000	2	2	1.000	0	0		0	0	0	3	1	0	1	0	8	+1	9.2
56	Devin Vassell	SAS		MEM	W	34:40	3	11	.273	2	4	.500	2	2	1.000	0	3	3	5	2	2	1	3	10	+11	9.1
57	Noah Clowney	BRK		BOS	L	22:41	4	8	.500	3	4	.750	2	4	.500	0	1	1	0	1	1	0	3	13	-14	9.0
58	Jaxson Hayes	LAL		UTA	W	15:02	3	3	1.000	0	0		2	3	.667	2	1	3	0	1	0	0	1	8	+13	9.0
59	Goga Bitadze	ORL		GSW	W	13:54	3	3	1.000	0	0		0	0		1	1	2	3	1	1	1	1	6	+8	8.5
60	Dillon Brooks	PHO	@	POR	W	25:38	5	11	.455	1	6	.167	1	2	.500	1	1	2	4	3	0	3	3	12	+16	8.5
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
61	Ziaire Williams	BRK		BOS	L	27:20	4	11	.364	2	7	.286	2	2	1.000	0	4	4	3	1	0	1	2	12	-4	8.4
62	Javonte Green	DET	@	ATL	W	28:37	3	5	.600	1	3	.333	2	2	1.000	0	3	3	1	2	0	2	0	9	+14	8.3
63	Tyrese Martin	BRK		BOS	L	17:53	3	6	.500	1	3	.333	1	2	.500	0	1	1	2	2	0	0	0	8	-6	8.3
64	Jaren Jackson Jr.	MEM	@	SAS	L	33:11	8	20	.400	2	7	.286	0	0		2	4	6	3	0	0	3	2	18	-4	8.1
65	Neemias Queta	BOS	@	BRK	W	22:51	3	5	.600	0	0		0	0		2	5	7	2	0	3	0	5	6	+5	8.1
66	Al Horford	GSW	@	ORL	L	27:10	2	6	.333	1	4	.250	4	4	1.000	0	6	6	1	2	1	2	2	9	-11	8.0
67	Kyle Anderson	UTA	@	LAL	L	20:02	2	5	.400	0	0		1	2	.500	1	2	3	5	2	0	0	2	5	+3	7.9
68	Sidy Cissoko	POR		PHO	L	28:07	2	7	.286	1	4	.250	3	3	1.000	1	2	3	5	2	0	2	2	8	+2	7.9
69	Jaylen Wells	MEM	@	SAS	L	26:38	4	9	.444	1	4	.250	0	0		0	1	1	2	2	0	0	1	9	-1	7.6
70	Yang Hansen	POR		PHO	L	13:08	4	7	.571	0	2	.000	1	1	1.000	1	4	5	3	0	1	3	0	9	+2	7.4
71	Egor Demin	BRK		BOS	L	23:15	4	10	.400	4	7	.571	0	0		1	2	3	4	1	0	4	1	12	-6	7.3
72	Ace Bailey	UTA	@	LAL	L	23:22	6	12	.500	1	6	.167	0	0		1	0	1	1	1	0	1	3	13	+6	7.2
73	Zach Edey	MEM	@	SAS	L	25:05	4	10	.400	0	0		0	0		5	6	11	2	0	2	3	3	8	+4	6.5
74	Ausar Thompson	DET	@	ATL	W	23:45	3	5	.600	0	0		0	0		0	2	2	0	1	3	0	3	6	-10	6.2
75	Nick Richards	PHO	@	POR	W	10:39	4	7	.571	0	0		0	0		2	0	2	0	0	1	0	2	8	-5	6.0
76	Chaz Lanier	DET	@	ATL	W	10:59	3	7	.429	3	7	.429	0	0		0	2	2	0	0	0	0	0	9	-2	5.9
77	Julian Champagnie	SAS		MEM	W	24:23	3	6	.500	2	5	.400	1	1	1.000	1	0	1	0	0	0	1	0	9	-7	5.7
78	Elijah Harkless	UTA	@	LAL	L	2:40	0	0		0	0		4	4	1.000	0	0	0	1	1	0	0	0	4	+5	5.7
79	Isaiah Collier	UTA	@	LAL	L	20:59	3	6	.500	0	0		3	3	1.000	0	2	2	6	0	0	4	3	9	-13	5.6
80	Royce O'Neale	PHO	@	POR	W	31:10	3	10	.300	3	10	.300	0	0		0	5	5	1	2	0	1	2	9	+19	5.6
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
81	Keaton Wallace	ATL		DET	L	13:08	2	4	.500	2	4	.500	1	2	.500	0	0	0	2	1	0	1	1	7	-5	5.6
82	Will Richard	GSW	@	ORL	L	15:18	2	2	1.000	1	1	1.000	1	2	.500	0	0	0	2	1	0	1	3	6	-4	5.2
83	Luka Garza	BOS	@	BRK	W	20:23	1	1	1.000	0	0		3	4	.750	2	3	5	0	1	0	1	4	5	+14	5.0
84	Paul Reed	DET	@	ATL	W	8:50	2	2	1.000	0	0		0	0		0	2	2	0	1	0	0	0	4	0	5.0
85	Jeremy Sochan	SAS		MEM	W	22:12	3	6	.500	2	3	.667	0	0		0	6	6	2	0	0	2	3	8	+10	5.0
86	Kentavious Caldwell-Pope	MEM	@	SAS	L	18:56	2	6	.333	0	3	.000	0	0		1	2	3	3	1	0	0	1	4	-16	4.6
87	Terance Mann	BRK		BOS	L	27:13	1	4	.250	0	2	.000	1	2	.500	1	3	4	7	0	0	1	3	3	-8	4.5
88	Robert Williams	POR		PHO	L	8:06	2	2	1.000	0	0		0	0		1	1	2	0	1	0	1	0	4	0	4.4
89	Luke Kennard	ATL		DET	L	17:05	1	2	.500	1	2	.500	0	0		0	0	0	5	1	0	1	3	3	+4	4.3
90	Gabe Vincent	LAL		UTA	W	16:01	2	3	.667	2	3	.667	0	0		0	0	0	1	0	0	0	3	6	+15	4.2
91	Luke Kornet	SAS		MEM	W	25:05	0	1	.000	0	0		0	0		2	2	4	3	1	0	0	1	0	-4	4.0
92	Rui Hachimura	LAL		UTA	W	25:42	3	8	.375	0	2	.000	0	0		2	2	4	1	0	0	0	1	6	+14	3.9
93	Nic Claxton	BRK		BOS	L	30:06	1	9	.111	0	0		5	8	.625	5	6	11	3	0	1	3	3	7	-10	3.8
94	Jamaree Bouyea	PHO	@	POR	W	3:26	1	2	.500	1	1	1.000	0	0		0	0	0	1	0	1	0	0	3	-3	3.4
95	David Jones García	SAS		MEM	W	6:55	1	1	1.000	0	0		0	0		0	1	1	2	0	0	0	0	2	+7	3.4
96	Carter Bryant	SAS		MEM	W	7:45	2	5	.400	1	3	.333	0	0		1	1	2	0	0	0	0	0	5	+1	3.3
97	Gary Payton II	GSW	@	ORL	L	10:15	2	3	.667	0	0		0	0		1	0	1	1	0	0	0	2	4	-15	3.3
98	Marcus Smart	LAL		UTA	W	17:09	2	5	.400	1	4	.250	0	0		1	2	3	1	0	0	0	3	5	+11	3.1
99	Vit Krejci	ATL		DET	L	36:06	3	9	.333	3	8	.375	0	0		0	3	3	2	0	0	2	3	9	+1	3.0
100	Moses Moody	GSW	@	ORL	L	29:34	2	6	.333	1	4	.250	1	2	.500	1	3	4	2	2	0	3	3	6	-3	3.0
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
101	Ron Holland	DET	@	ATL	W	18:35	1	2	.500	0	1	.000	0	0		0	1	1	1	1	0	0	1	2	+13	2.6
102	John Konchar	MEM	@	SAS	L	13:47	0	2	.000	0	2	.000	0	0		1	2	3	3	1	0	0	1	0	-5	2.6
103	Cody Williams	UTA	@	LAL	L	20:36	2	5	.400	0	3	.000	0	0		0	0	0	0	1	1	0	1	4	-14	2.6
104	Baylor Scheierman	BOS	@	BRK	W	13:22	1	2	.500	1	2	.500	0	0		0	2	2	1	0	0	0	2	3	+3	2.5
105	Isaiah Livers	PHO	@	POR	W	12:38	1	3	.333	1	3	.333	2	3	.667	0	2	2	0	0	0	0	3	5	+3	2.3
106	Brandin Podziemski	GSW	@	ORL	L	26:31	2	7	.286	1	2	.500	0	0		1	5	6	0	0	0	0	2	5	-7	2.3
107	Rasheer Fleming	PHO	@	POR	W	10:00	0	4	.000	0	2	.000	4	4	1.000	3	3	6	0	0	0	2	0	4	-6	2.2
108	Kris Murray	POR		PHO	L	25:08	1	4	.250	1	3	.333	0	0		2	2	4	0	0	0	0	1	3	-29	2.2
109	Jordan Walsh	BOS	@	BRK	W	11:13	2	2	1.000	0	0		0	0		0	1	1	0	0	0	0	4	4	-12	2.1
110	Quinten Post	GSW	@	ORL	L	12:09	1	4	.250	0	3	.000	0	0		2	1	3	1	0	0	0	0	2	0	2.0
111	Duop Reath	POR		PHO	L	10:25	1	2	.500	1	2	.500	0	0		0	0	0	0	0	0	0	1	3	+5	1.6
112	Rayan Rupert	POR		PHO	L	8:27	1	2	.500	0	1	.000	1	2	.500	0	1	1	0	1	0	1	1	3	+2	1.5
113	Brice Sensabaugh	UTA	@	LAL	L	17:23	1	6	.167	1	6	.167	0	0		1	0	1	3	2	0	1	5	3	-16	1.0
114	Jock Landale	MEM	@	SAS	L	17:33	2	9	.222	0	2	.000	0	3	.000	4	3	7	2	1	1	2	3	4	-17	0.9
115	Adou Thiero	LAL		UTA	W	3:33	1	1	1.000	0	0		0	0		0	0	0	0	0	0	0	2	2	-7	0.9
116	Bronny James	LAL		UTA	W	3:33	1	1	1.000	1	1	1.000	0	0		0	0	0	2	0	0	3	1	3	-7	0.7
117	Xavier Tillman Sr.	BOS	@	BRK	W	4:47	0	0		0	0		0	0		0	0	0	1	0	0	0	0	0	-5	0.7
118	Nolan Traoré	BRK		BOS	L	1:56	0	0		0	0		0	0		0	0	0	1	0	0	0	0	0	-2	0.7
119	Kevin Love	UTA	@	LAL	L	13:32	0	2	.000	0	2	.000	0	0		1	3	4	0	0	1	0	2	0	-8	0.1
120	Jamal Cain	ORL		GSW	W	0:09	0	0		0	0		0	0		0	0	0	0	0	0	0	0	0	-3	0.0
Rk	Player	Tm	 	Opp	 	MP	FG	FGA	FG%	3P	3PA	3P%	FT	FTA	FT%	ORB	DRB	TRB	AST	STL	BLK	TOV	PF	PTS	+/-	GmSc
121	Maxi Kleber	LAL		UTA	W	2:40	0	0		0	0		0	0		0	0	0	0	0	0	0	0	0	-5	0.0
122	Dalton Knecht	LAL		UTA	W	3:33	0	0		0	0		0	0		0	0	0	0	0	0	0	0	0	-7	0.0
123	Asa Newell	ATL		DET	L	1:55	0	0		0	0		0	0		0	0	0	0	0	0	0	0	0	-4	0.0
124	Danny Wolf	BRK		BOS	L	1:56	0	0		0	0		0	0		0	0	0	0	0	0	0	0	0	-2	0.0
125	Lindy Waters III	SAS		MEM	W	4:51	0	2	.000	0	2	.000	0	0		0	3	3	0	0	0	0	0	0	-4	-0.5
126	Buddy Hield	GSW	@	ORL	L	15:12	1	3	.333	0	1	.000	0	0		0	0	0	0	0	0	1	0	2	-5	-0.7
127	Nigel Hayes-Davis	PHO	@	POR	W	3:36	0	3	.000	0	1	.000	0	0		2	1	3	0	0	0	0	1	0	-3	-0.8
128	Toumani Camara	POR		PHO	L	32:15	2	10	.200	2	9	.222	0	0		1	1	2	3	1	0	4	3	6	-17	-1.3
129	Caleb Houstan	ATL		DET	L	3:23	0	2	.000	0	1	.000	0	0		0	0	0	0	0	0	0	1	0	-9	-1.8
130	Jonathan Isaac	ORL		GSW	W	6:49	0	2	.000	0	1	.000	0	0		1	1	2	0	0	0	1	1	0	+3	-1.8
131	Drake Powell	BRK		BOS	L	24:28	1	5	.200	0	2	.000	1	1	1.000	0	1	1	1	1	0	2	5	3	-2	-2.1
132	Jalen Wilson	BRK
"""

# =======================
# 2) PARSER
# =======================

SEASON_LABEL = "2025-26"



# =======================
# 3) DB HELPERS
# =======================


def upsert_boxscores(
    engine: Engine,
    rows: List[Dict],
    date_1: date,
    date_2: date,
) -> None:
    summary = replace_player_boxscores(
        engine,
        rows,
        dates=[date_1, date_2],
        season_label=SEASON_LABEL,
    )

    print("Boxscores summary grouped by team:")
    for row in summary:
        print(
            f"{row.game_date} {row.team}: {row.total_pts} pts "
            f"({row.players} players)"
        )


def main() -> None:
    engine = get_pg_engine()

    date_1 = date(2025, 11, 17)
    date_2 = date(2025, 11, 18)

    rows_17 = parse_raw_boxscores(RAW_BOXSCORES_2025_11_17, date_1)
    rows_18 = parse_raw_boxscores(RAW_BOXSCORES_2025_11_18, date_2)

    all_rows = rows_17 + rows_18
    print(
        f"Parsed {len(rows_17)} rows for 2025-11-17 and {len(rows_18)} for 2025-11-18"
    )

    upsert_boxscores(engine, all_rows, date_1, date_2)


if __name__ == "__main__":
    main()
