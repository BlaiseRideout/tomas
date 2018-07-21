$(function() {
	$('input[data-type="date"]').datepicker({
		"dateFormat": "yy-mm-dd",
		"showAnim": "slideDown",
		"changeMonth": true,
		"changeYear": true
	});
	fillSelect("/countries", "select.countryselect", "Code", "Id", function() {
		$(".countryselect").change(function(event) {
			$(this).parent().next(".flag").html(
				$(this).data("selectData")[this.selectedIndex]["Flag_Image"]);
			$(this).next(".countryname").text(
				$(this).data("selectData")[this.selectedIndex]["Name"]);
			update_state(event);
		});
	});

	function update_state(event, del) {
		state = current_state();
		if (del) {
			state['Id'] = -1
		}
		if (is_info_valid(state) || del) {
			var URLparts = window.location.toString().split('/'),
				len = URLparts.length;
			if (len = 0 || URLparts[len - 1] != $("#tournamentSettings").data("tournamentid")) {
				URLparts.push($("#tournamentSettings").data("tournamentid"));
			}
			$.post(URLparts.join("/"), state,
				function(data) {
					if (data["message"])
						$.notify(data["message"], data["status"]);
					if (data["status"] === "load") {
						window.location.assign(data["URL"])
					}
				});
		}
		else {
			console.log('State is invalid');
		}
	};

	function current_state() {
		var state = {};
		$(":input").filter(function() {
			return $.hasData(this)
		}).each(
			function(i, elem) {
				if ($(elem).data("colname")) {
					state[$(elem).data("colname")] = $(elem).val();
				};
			});
		state["Id"] = $("#tournamentSettings").data("tournamentid");
		return state;
	};

	function is_info_valid(state) {
		var invalid = [];
		if (!state['Name']) {
			$("input#namefield").removeClass("good").addClass("bad");
			invalid.push('Name');
		}
		else {
			$("input#namefield").removeClass("bad").addClass("good");
		};
		var datepattern = /\d{4}-\d{2}-\d{2}/;
		$("input.hasDatepicker").each(function(i, e) {
			var val = $(e).val();
			if (val.match(datepattern) &&
				1 <= val.slice(5, 7) && val.slice(5, 7) <= 12 &&
				1 <= val.slice(8, 10) && val.slice(8, 10) <= 31) {
				$(e).removeClass("bad").addClass("good");
			}
			else {
				$(e).removeClass("good").addClass("bad");
				invalid.push($(e).data('colname'));
			};
		});
		if ($("input#endfield").val() < $("input#startfield").val()) {
			$("input#endfield").removeClass("good").addClass("bad");
			invalid.push($("input#endfield").data('colname'));
		};
		if (invalid.length == 1) {
			$.notify('Field ' + invalid[0] + ' is not valid', 'warn');
		}
		else if (invalid.length) {
			$.notify('Fields ' + invalid.join(', ') + ' are not valid',
				'warn');
		};
		return invalid.length == 0;
	};

	/* Set up action handlers after loading */
	$(":input").change(update_state).keyup(update_state);
	$("#deletetournamentbutton").click(function(e) {
		update_state(e, true)
	});
	/* Set keyboard focus to tournament name if it's empty */
	$("#namefield").filter(function() {
		return $(this).val() == ''
	}).focus();
});
