Теперь можно удалить следующие файлы (они больше не используются):

decap_placer/geometry/strategies.py

decap_placer/geometry/strategy_factory.py

decap_placer/geometry/relax.py (можно оставить, если используется где-то ещё, но в ручной стратегии не нужен)

decap_placer/geometry/boundary.py (если не используется для термовиа, но термовиа используют closest_point_on_polygon? Нет, они используют compute_thermal_via_grid, который не зависит от boundary. Так что можно удалить и boundary.py, и placement.py (если они не используются в других частях). Однако closest_point_on_polygon всё ещё может вызываться из via_planner.py? В новой версии он не вызывается, но для термовиа он не нужен. Поэтому можно смело удалять boundary.py и placement.py.

decap_placer/placement/services/position_calculator.py (заменён на manual_position_calculator.py)

decap_placer/placement/services/power_pin_orienter.py (не используется)

decap_placer/placement/services/spacing_relaxer.py (не используется)

decap_placer/placement/power_pin.py (не используется)

Если вы хотите оставить их для истории или возможного будущего использования, можно переместить в папку old/.

