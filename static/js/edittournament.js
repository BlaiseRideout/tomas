$(function() {
	$('input[data-type="date"]').datepicker({
		"dateFormat": "yy-mm-dd",
		"showAnim": "slideDown",
		"changeMonth": true,
		"changeYear": true
	});
	fillSelect("/countries", "span.countryselect", "Code", "Id", function() {
		$(".countryselect").change(function() {
			$(this).parent().next(".flag").html(
				$(this).data("selectData")[$(this).val() - 1]["Flag_Image"]);
			$(this).next(".countryname").text(
				$(this).data("selectData")[$(this).val() - 1]["Name"]);
		});
	});

	function update_state(event, del) {
		state = current_state();
		if (del) {
			state['Id'] = -1
		}
		if (is_info_valid(state) || del) {
			$.post("", state,
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
		/*
		console.log('State vector: {');
		for (prop in state) {console.log('  ' + prop + ': ' + state[prop])};
		console.log('}');
		*/
		return state;
	};

	function is_info_valid(state) {
		var valid = true;
		if (!state['Name']) {
			$("input#namefield").removeClass("good").addClass("bad");
			valid = false;
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
				valid = false;
			};
		});
		if ($("input#endfield").val() < $("input#startfield").val()) {
			$("input#endfield").removeClass("good").addClass("bad");
			valid = false;
		};
		return valid
	};

	/* Set up action handlers after loading */
	$(":input").change(update_state);
	$("#deletetournamentbutton").click(function(e) {
		update_state(e, true)
	});
});
