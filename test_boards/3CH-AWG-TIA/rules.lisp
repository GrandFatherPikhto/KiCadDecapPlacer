(version 1)

(rule "Int2_rule"
    (condition "A.Layer == 'Int2.Cu'")
    (constraint zone_connection solid)
	(constraint track_width (min 3mm) (opt 3mm))
	(constraint clearance (min 0.2mm) (opt 0.3mm)))

(rule "Power_Neckdown_FPGA_rule"
    (condition "A.Type == 'Track' && A.insideArea('FPGA_ESCAPE') && (A.Layer == 'B.Cu' || A.Layer == 'F.Cu') && A.hasNetclass('Power_*')")
    (constraint track_width (min 0.254mm) (opt 0.254mm) (max 0.254mm)))
