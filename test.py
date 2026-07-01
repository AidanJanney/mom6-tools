from mom6_tools import init_domain

case = init_domain(diag_table="/glade/work/ajanney/Software/mom6-tools/diag_tables/diag_table_global", output_dir="/glade/derecho/scratch/gmarques/archive/b.e30_alpha08b.B1850C_LTso.ne30_t232_wgx3.328/ocn/hist")
case.summary()

result = case.surface(start="0010-01-01", end="0012-01-01", save="./output/")
print(result)