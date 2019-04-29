--SQL Name: NEDS_LNCEL_FDD.sql
--Update History:
--2018-3-22: initial version by gaozw
--2019-4-29: update earfcn using singleOAM by gaozw

select
co_lnbts.co_gid lnbts_id
,co_lncel.co_gid lncel_id
,co_lnbts.co_object_instance enb_id
,co_lncel.co_object_instance lcr_id
--LNCEL parameters
,lncel.LNCEL_EUTRA_CEL_ID eci
--,case when substr(co_lncel.co_sys_version, 0, 2) = 'FL' then lncel.LNCEL_EARFCN_DL else lncel.LNCEL_EARFCN end earfcn
--LNCEL/cellTechnology: FDD (0), TDD (1), NB-IoT-FDD (3)
,case when lncel.LNCEL_CLL_TECHNOLOGY = 0 then lncel_fdd.LNCEL_FDD_EARFCN_DL else lncel.LNCEL_EARFCN_DL end earfcn
,lncel.LNCEL_PHY_CELL_ID pci
,lncel.lncel_tac tac
--A3/A5
,lncel.LNCEL_THLD_1 th1
,lncel.LNCEL_A_3_OFFS a3_off
,lncel.LNCEL_HYS_A_3_OFFS hys_a3_off
,lncel.LNCEL_A_3_REP_INT a3_rep_int
,lncel.LNCEL_A_3_TTT a3_ttt
,lncel.LNCEL_THLD_3 a5_th3
,lncel.LNCEL_THLD_3_A a5_th3a
,lncel.LNCEL_HYS_THLD_3 hys_a5_th3
,lncel.LNCEL_A_5_REP_INT a5_rep_int
,lncel.LNCEL_A_5_TTT a5_ttt
--A1/A2 for inter-frequency
,lncel.LNCEL_THLD_2_IFREQ a2_th2_if
,lncel.LNCEL_HT2I_86 hys_a2_th2_if
,lncel.LNCEL_A2TAIM_4 a2_ttt
,lncel.LNCEL_THLD_2_A a1_th2a
,lncel.LNCEL_HYS_THLD_2_A hys_a1_th2a
,lncel.LNCEL_A1TDIM_3 a1_ttt

from
ctp_common_objects co_lncel
,ctp_common_objects co_lncel_fdd
,ctp_common_objects co_lnbts
,c_lte_lncel lncel
,c_lte_lncel_fdd lncel_fdd

where
lncel.conf_id = 1 and lncel.obj_gid = co_lncel.co_gid
and lncel_fdd.conf_id = 1 and lncel_fdd.obj_gid = co_lncel_fdd.co_gid
and co_lncel_fdd.co_parent_gid = co_lncel.co_gid
and co_lncel.co_parent_gid = co_lnbts.co_gid
and lncel.LNCEL_EUTRA_CEL_ID is not null
